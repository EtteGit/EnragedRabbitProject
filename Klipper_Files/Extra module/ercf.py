# Enraged Rabbit Carrot Feeder
#
# Copyright (C) 2021  Ette
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
import math
from . import pulse_counter
from . import force_move
import toolhead
import copy

class EncoderCounter:

    def __init__(self, printer, pin, sample_time, poll_time, encoder_steps):
        self._last_time = self._last_count = None
        self._counts = 0
        self._encoder_steps = encoder_steps
        self._counter = pulse_counter.MCU_counter(printer, pin, sample_time,
                                    poll_time)
        self._counter.setup_callback(self._counter_callback)

    def _counter_callback(self, time, count, count_time):
        if self._last_time is None:  # First sample
            self._last_time = time
        elif count_time > self._last_time:
            self._last_time = count_time
            self._counts += count - self._last_count
        else:  # No counts since last sample
            self._last_time = time
        self._last_count = count

    def get_counts(self):
        return self._counts

    def get_distance(self):
        return (self._counts/2.) * self._encoder_steps

    def set_distance(self, new_distance):
        self._counts = int( ( new_distance / self._encoder_steps ) * 2. )

    def reset_counts(self):
        self._counts = 0.

class Ercf:

    LONG_MOVE_THRESHOLD = 70.
    MACRO_SERVO_UP = "ERCF_SERVO_UP"
    MACRO_SERVO_DOWN = "ERCF_SERVO_DOWN"
    MACRO_UNSELECT_TOOL = "ERCF_UNSELECT_TOOL"
    MACRO_PAUSE = "ERCF_PAUSE"

    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.printer.register_event_handler("klippy:connect",
                                            self.handle_connect)
        # Manual steppers
        self.selector_stepper = self.gear_stepper = None
        self.encoder_pin = config.get('encoder_pin')
        self.encoder_resolution = config.getfloat('encoder_resolution', 1.5,
                                            above=0.)
        self._counter = EncoderCounter(self.printer, self.encoder_pin, 0.01,
                                            0.00001, self.encoder_resolution)
        
        # Parameters
        self.long_moves_speed = config.getfloat('long_moves_speed', 100.)
        self.long_moves_accel = config.getfloat('long_moves_accel', 400.)
        self.short_moves_speed = config.getfloat('short_moves_speed', 25.)
        self.short_moves_accel = config.getfloat('short_moves_accel', 400.)
        # GCODE commands
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command('ERCF_CALIBRATE_ENCODER',
                    self.cmd_ERCF_CALIBRATE_ENCODER,
                    desc=self.cmd_ERCF_CALIBRATE_ENCODER_help)
        self.gcode.register_command('ERCF_RESET_ENCODER_COUNTS',
                    self.cmd_ERCF_RESET_ENCODER_COUNTS,
                    desc=self.cmd_ERCF_RESET_ENCODER_COUNTS_help)
        self.gcode.register_command('ERCF_LOAD',
                    self.cmd_ERCF_LOAD,
                    desc=self.cmd_ERCF_LOAD_help)
        self.gcode.register_command('ERCF_UNLOAD',
                    self.cmd_ERCF_UNLOAD,
                    desc=self.cmd_ERCF_UNLOAD_help)
        self.gcode.register_command('ERCF_BUZZ_GEAR_MOTOR',
                    self.cmd_ERCF_BUZZ_GEAR_MOTOR,
                    desc=self.cmd_ERCF_BUZZ_GEAR_MOTOR_help)
        self.gcode.register_command('ERCF_HOME_EXTRUDER',
                    self.cmd_ERCF_HOME_EXTRUDER,
                    desc=self.cmd_ERCF_HOME_EXTRUDER_help)
        self.gcode.register_command('ERCF_SET_STEPS',
                    self.cmd_ERCF_SET_STEPS,
                    desc=self.cmd_ERCF_SET_STEPS_help)
        self.gcode.register_command('ERCF_GET_SELECTOR_POS',
                    self.cmd_ERCF_GET_SELECTOR_POS,
                    desc=self.cmd_ERCF_GET_SELECTOR_POS_help)
        self.gcode.register_command('ERCF_MOVE_SELECTOR',
                    self.cmd_ERCF_MOVE_SELECTOR,
                    desc=self.cmd_ERCF_MOVE_SELECTOR_help)
        self.gcode.register_command('ERCF_ENDLESSSPOOL_UNLOAD',
                    self.cmd_ERCF_ENDLESSSPOOL_UNLOAD,
                    desc=self.cmd_ERCF_ENDLESSSPOOL_UNLOAD_help)
        self.gcode.register_command('ERCF_FINALIZE_LOAD',
                    self.cmd_ERCF_FINALIZE_LOAD,
                    desc=self.cmd_ERCF_FINALIZE_LOAD_help)

    def handle_connect(self):
        self.toolhead = self.printer.lookup_object('toolhead')
        for manual_stepper in self.printer.lookup_objects('manual_stepper'):
            rail_name = manual_stepper[1].get_steppers()[0].get_name()
            if rail_name == 'manual_stepper selector_stepper':
                self.selector_stepper = manual_stepper[1]
            if rail_name == 'manual_stepper gear_stepper':
                self.gear_stepper = manual_stepper[1]
        if self.selector_stepper is None:
            raise config.error(
                "Manual_stepper selector_stepper must be specified")
        if self.gear_stepper is None:
            raise config.error(
                "Manual_stepper gear_stepper must be specified")
        self.ref_step_dist=self.gear_stepper.rail.steppers[0].get_step_dist()

    def get_status(self, eventtime):
        encoder_pos = float(self._counter.get_distance())
        return {'encoder_pos': encoder_pos}

    def _sample_stats(self, values):
        mean = 0.
        stdev = 0.
        vmin = 0.
        vmax = 0.
        if values:
            mean = sum(values) / len(values)
            diff2 = [( v - mean )**2 for v in values]
            stdev = math.sqrt( sum(diff2) / ( len(values) - 1 ))
            vmin = min(values)
            vmax = max(values)
        return {'mean': mean, 'stdev': stdev, 'min': vmin,
                        'max': vmax, 'range': vmax - vmin}

    def _gear_stepper_move_wait(self, dist, wait=True, speed=None, accel=None):
        self.gear_stepper.do_set_position(0.)
        is_long_move = abs(dist) > self.LONG_MOVE_THRESHOLD
        if speed is None:
            speed = self.long_moves_speed if is_long_move \
                    else self.short_moves_speed
        if accel is None:
            accel = self.long_moves_accel if is_long_move \
                    else self.short_moves_accel
        self.gear_stepper.do_move(dist, speed, accel, True)
        if wait :
            self.toolhead.wait_moves()

    def _selector_stepper_move_wait(self, dist, home=0, wait=True,
                                    speed=80., accel=1800):
        homing_string = ""
        wait_string = ""
        if home != 0:
            homing_string = (" STOP_ON_ENDSTOP=%s" % home)
        if not wait:
            wait_string = (" SYNC=0")
        command_string = ("MANUAL_STEPPER STEPPER=selector_stepper"
                         " SPEED=%s ACCEL=%s MOVE=%s%s%s"
                         % (speed, accel, dist, homing_string, wait_string))
        self.gcode.run_script_from_command(command_string)

    cmd_ERCF_CALIBRATE_ENCODER_help = "Calibration routine for the ERCF encoder"
    def cmd_ERCF_CALIBRATE_ENCODER(self, gcmd):
        dist = gcmd.get_float('DIST', 500., above=0.)
        repeats = gcmd.get_int('RANGE', 5, minval=1)
        speed = gcmd.get_float('SPEED', self.long_moves_speed, above=0.)
        accel = gcmd.get_float('ACCEL', self.long_moves_accel, above=0.)
        plus_values, min_values = [], []

        for x in range(repeats):
            # Move forward
            self._counter.reset_counts()
            self._gear_stepper_move_wait(dist, True, speed, accel)
            plus_values.append(self._counter.get_counts())
            self.gcode.respond_info("+ counts =  %.3f"
                        % (self._counter.get_counts()))
            # Move backward
            self._counter.reset_counts()
            self._gear_stepper_move_wait(-dist, True, speed, accel)
            min_values.append(self._counter.get_counts())
            self.gcode.respond_info("- counts =  %.3f"
                        % (self._counter.get_counts()))

        gcmd.respond_info("Load direction: mean=%(mean).2f stdev=%(stdev).2f"
                          " min=%(min)d max=%(max)d range=%(range)d"
                          % self._sample_stats(plus_values))
        gcmd.respond_info("Unload direction: mean=%(mean).2f stdev=%(stdev).2f"
                          " min=%(min)d max=%(max)d range=%(range)d"
                          % self._sample_stats(min_values))

        mean_plus = self._sample_stats(plus_values)['mean']
        mean_minus = self._sample_stats(min_values)['mean']
        half_mean = ( float(mean_plus) + float(mean_minus) ) / 4

        if half_mean == 0:
            gcmd.respond_info("No counts measured. Ensure a tool was selected " +
                              "before running calibration and that your encoder " +
                              "is working properly")
            return

        resolution = dist / half_mean
        old_result = half_mean * self.encoder_resolution
        new_result = half_mean * resolution

        gcmd.respond_info("Before calibration measured length = %.6f" 
                          % old_result)
        gcmd.respond_info("Resulting resolution for the encoder = %.6f" 
                          % resolution)
        gcmd.respond_info("After calibration measured length = %.6f" 
                          % new_result)

    cmd_ERCF_HOME_EXTRUDER_help = "Home the filament tip on the toolhead sensor"
    def cmd_ERCF_HOME_EXTRUDER(self, gcmd):
        homing_length = gcmd.get_float('TOTAL_LENGTH', 100., above=0.)
        step_length = gcmd.get_float('STEP_LENGTH', 1., above=0.)
        both_in_sync = True
        homing_speed = 25.
        sensor = self.printer.lookup_object(
                    "filament_switch_sensor toolhead_sensor")
        sensor_state = bool(sensor.runout_helper.filament_present)
        if sensor_state :
            step_length = -step_length
            both_in_sync = False # Do not move the ERCF if move is an unload
        for step in range( int( homing_length / abs(step_length) ) + 1 ):
            if bool(sensor.runout_helper.filament_present) == sensor_state:
                if step * abs(step_length) >= homing_length :
                    self.gcode.respond_info(
                                    "Unable to reach the toolhead sensor")
                    self.gcode.run_script_from_command(self.MACRO_UNSELECT_TOOL)
                    self.gcode.run_script_from_command(self.MACRO_PAUSE)
                    break
                if both_in_sync :
                    self.gear_stepper.do_set_position(0.)
                    self.gear_stepper.do_move(step_length, homing_speed, 
                                                self.short_moves_accel, False)
                pos = self.toolhead.get_position()
                pos[3] += step_length
                self.toolhead.manual_move(pos, homing_speed)
                self.toolhead.dwell(0.2)
            else:
                self.toolhead.wait_moves()
                self.gear_stepper.do_set_position(0.)
                break

    cmd_ERCF_RESET_ENCODER_COUNTS_help = "Reset the ERCF encoder counts"
    def cmd_ERCF_RESET_ENCODER_COUNTS(self, gcmd):
        self._counter.reset_counts() 

    cmd_ERCF_BUZZ_GEAR_MOTOR_help = "Buzz the ERCF gear motor"
    def cmd_ERCF_BUZZ_GEAR_MOTOR(self, gcmd):
        self._counter.reset_counts()
        self._gear_stepper_move_wait(2., False)
        self._gear_stepper_move_wait(-2.)

    cmd_ERCF_LOAD_help = "Load filament from ERCF to the toolhead"
    def cmd_ERCF_LOAD(self, gcmd):
        req_length = gcmd.get_float('LENGTH', 0.)
        iterate = False if req_length == 0. else True
        self.toolhead.wait_moves()
        self._counter.reset_counts()
        self._gear_stepper_move_wait(self.LONG_MOVE_THRESHOLD)

        if self._counter.get_distance() <= 6.:
            self.gcode.respond_info("Error loading filament to ERCF, no"
                                    " filament detected during load sequence,"
                                    " retry loading...")
            # Reengage gears and retry
            self.gcode.run_script_from_command(self.MACRO_SERVO_UP)
            self.gcode.run_script_from_command(self.MACRO_SERVO_DOWN)
            self._gear_stepper_move_wait(self.LONG_MOVE_THRESHOLD)

            if self._counter.get_distance() <= 6.:
                self.gcode.respond_info("Still no filament loaded in the ERCF,"
                                        " calling %s..."
                                        % self.MACRO_PAUSE)
                self.gcode.run_script_from_command(self.MACRO_UNSELECT_TOOL)
                self.gcode.run_script_from_command(self.MACRO_PAUSE)
                return
            else :
                self.gcode.respond_info("Filament loaded in ERCF after retry")
        
        if req_length != 0:
            counter_distance = self._counter.get_distance()
            self._gear_stepper_move_wait(req_length - counter_distance)
            counter_distance = self._counter.get_distance()
            
            self.gcode.respond_info(
                            "Load move done, requested = %.1f, measured = %.1f"
                            %(req_length, counter_distance))
            diff_distance = req_length - counter_distance
            
            if diff_distance <= 4. or not iterate :
                # Measured move is close enough or no iterations : load succeeds
                return

            # Do the correction moves
            for retry_attempts in range(2):
                self._gear_stepper_move_wait(diff_distance)
                counter_distance = self._counter.get_distance()
                self.gcode.respond_info("Correction load move done,"
                                        " requested = %.1f, measured = %.1f"
                                        %(req_length, counter_distance))
                diff_distance = req_length - counter_distance
                if diff_distance <= 4.:
                    # Measured move is close enough : load succeeds
                    return
                if diff_distance > self.LONG_MOVE_THRESHOLD:
                    break
            # Load failed
            self.gcode.respond_info(
                "Too much slippage detected during the load,"
                " please check the ERCF, calling %s..."
                % self.MACRO_PAUSE)
            self.gcode.run_script_from_command(self.MACRO_UNSELECT_TOOL)
            self.gcode.run_script_from_command(self.MACRO_PAUSE)

    cmd_ERCF_UNLOAD_help = "Unload filament and park it in the ERCF"
    def cmd_ERCF_UNLOAD(self, gcmd):
        # Define unload move parameters
        iterate = True
        buffer_length = 30.
        homing_move = gcmd.get_int('HOMING', 0, minval=0, maxval=1)
        unknown_state = gcmd.get_int('UNKNOWN', 0, minval=0, maxval=1)
        req_length = gcmd.get_float('LENGTH', 1200.)
        self.toolhead.wait_moves()
        # i.e. long move that will be fast and iterated using the encoder
        if req_length > self.LONG_MOVE_THRESHOLD: 
            req_length = req_length - buffer_length
        else:
            iterate = False
        if unknown_state :
            iterate = False
            self._counter.reset_counts()
            self._gear_stepper_move_wait(-req_length)
            homing_move = 1
        if homing_move :
            iterate = False
            for step in range( int(req_length / 15.) ):
                self._counter.reset_counts()
                self._gear_stepper_move_wait(-15.)
                delta = 15. - self._counter.get_distance()
                # Filament is now out of the encoder
                if delta >= 3. :
                    self._counter.reset_counts()
                    self._gear_stepper_move_wait(-(23. - delta))
                    if self._counter.get_distance() < 5. :
                        return
        else:
            self._counter.reset_counts()
            self._gear_stepper_move_wait(-req_length)
        if iterate :
            counter_distance = self._counter.get_distance()
            self.gcode.respond_info(
                        "Unload move done, requested = %.1f, measured = %.1f"
                        % (req_length, counter_distance) )
            delta_length = req_length - counter_distance
            if delta_length >= 3.0:
                self._gear_stepper_move_wait(-delta_length)
                counter_distance = self._counter.get_distance()
                self.gcode.respond_info("Correction unload move done,"
                                        " requested = %.1f, measured = %.1f"
                                        %(req_length, counter_distance))
                if ( req_length - counter_distance ) >= 15. :
                    # Unload failed
                    self.gcode.respond_info(
                        "Too much slippage detected during the unload,"
                        " please check the ERCF, calling %s..."
                        % self.MACRO_PAUSE)
                    self.gcode.run_script_from_command(self.MACRO_UNSELECT_TOOL)
                    self.gcode.run_script_from_command(self.MACRO_PAUSE)
                    return
            # Final move to park position
            for step in range( int(buffer_length / 15.) + 1 ):
                self._counter.reset_counts()
                self._gear_stepper_move_wait(-15.)
                delta = 15. - self._counter.get_distance()
                # Filament is now out of the encoder
                if delta >= 3. :
                    self._counter.reset_counts()
                    self._gear_stepper_move_wait(-(23. - delta))
                    if self._counter.get_distance() < 5. :
                        return
            # Filament stuck in encoder
            self.gcode.respond_info(
                "Unable to get the filament out of the encoder cart,"
                " please check the ERCF, calling %s..."
                % self.MACRO_PAUSE)
            self.gcode.run_script_from_command(self.MACRO_UNSELECT_TOOL)
            self.gcode.run_script_from_command(self.MACRO_PAUSE)

    cmd_ERCF_SET_STEPS_help = "Changes the steps/mm for the ERCF gear motor"
    def cmd_ERCF_SET_STEPS(self, gcmd):
        ratio = gcmd.get_float('RATIO', 1., above=0.)
        new_step_dist = self.ref_step_dist / ratio
        stepper = self.gear_stepper.rail.steppers[0]
        if hasattr(stepper, "set_rotation_distance"):
            new_rotation_dist = new_step_dist * stepper.get_rotation_distance()[1]
            stepper.set_rotation_distance(new_rotation_dist)
        else:
            # bw compatibilty for old klipper versions
            stepper.set_step_dist(new_step_dist)

    cmd_ERCF_GET_SELECTOR_POS_help = "Report the selector motor position"
    def cmd_ERCF_GET_SELECTOR_POS(self, gcmd):
        ref_pos = gcmd.get_float('REF', 0.)
        self.selector_stepper.do_set_position(0.)
        init_position = self.selector_stepper.steppers[0].get_mcu_position()
        #self._selector_stepper_move_wait(-ref_pos, 1, True, 50.)
        self.command_string = (
                        "MANUAL_STEPPER STEPPER=selector_stepper SPEED=40"
                        " MOVE=-" + str(ref_pos) + " STOP_ON_ENDSTOP=1")
        self.gcode.run_script_from_command(self.command_string)

        current_position = self.selector_stepper.steppers[0].get_mcu_position()
        traveled_position = abs(current_position - init_position) \
                * self.selector_stepper.steppers[0].get_step_dist()
        self.gcode.respond_info("Selector position = %.1f "
                                %(traveled_position))

    cmd_ERCF_MOVE_SELECTOR_help = "Move the ERCF selector"
    def cmd_ERCF_MOVE_SELECTOR(self, gcmd):
        target = gcmd.get_float('TARGET', 0.)
        selector_steps = self.selector_stepper.steppers[0].get_step_dist()
        init_position = self.selector_stepper.get_position()[0]
        init_mcu_pos = self.selector_stepper.steppers[0].get_mcu_position()
        target_move = target - init_position
        self._selector_stepper_move_wait(target, 2)
        mcu_position = self.selector_stepper.steppers[0].get_mcu_position()
        travel = ( mcu_position - init_mcu_pos ) * selector_steps
        delta = abs( target_move - travel )
        if delta <= 2.0 :
            commanded = self.selector_stepper.steppers[0].get_commanded_position()
            frommcu = travel + init_position
            self.gcode.respond_info("target = %.1f init_position = %.1f commanded = %.1f frommcu = %.1f"
                                %(target, init_position, commanded, frommcu))
            self.selector_stepper.do_set_position( init_position + travel )
            self._selector_stepper_move_wait(target)
            return
        # Issue detected
        if abs( travel ) <= 2.3 :
            # Filament stuck in the selector
            self.gcode.respond_info(
                "Selector is blocked by inside filament,"
                " trying to recover...")
            # Realign selector
            self.selector_stepper.do_set_position(0.)
            self.selector_stepper.do_move(-travel, 50, 200, True)
            self.toolhead.wait_moves()
            
            # Engage filament to the encoder
            self.gcode.run_script_from_command(self.MACRO_SERVO_DOWN)
            self.gcode.run_script_from_command("ERCF_LOAD LENGTH=45")
            self.gcode.run_script_from_command("G4 P50")
            # Try to unload
            self.gcode.run_script_from_command("ERCF_UNLOAD LENGTH=68")
            self.gcode.run_script_from_command(self.MACRO_SERVO_UP)
            # Check if selector can reach proper target
            self.gcode.run_script_from_command("ERCF_HOME_SELECTOR")
            init_position = self.selector_stepper.get_position()[0]
            init_mcu_pos = self.selector_stepper.steppers[0].get_mcu_position()
            target_move = target - init_position
            self._selector_stepper_move_wait(target, 2)
            mcu_position = self.selector_stepper.steppers[0].get_mcu_position()
            travel = ( mcu_position - init_mcu_pos ) *selector_steps
            delta = abs( target_move - travel )
            if delta <= 2.0 :
                commanded = self.selector_stepper.steppers[0].get_commanded_position()
                frommcu = travel + init_position
                self.gcode.respond_info("target = %.1f init_position = %.1f commanded = %.1f frommcu = %.1f"
                                    %(target, init_position, commanded, frommcu))
                self.selector_stepper.do_set_position( init_position + travel )
                self._selector_stepper_move_wait(target)
                return
            else :
                # Selector path is still blocked
                self.gcode.respond_info(
                    "Selector recovery failed, please check the ERCF,"
                    " calling %s..."
                    % self.MACRO_PAUSE)
                self.gcode.run_script_from_command(self.MACRO_UNSELECT_TOOL)
                self.gcode.run_script_from_command(self.MACRO_PAUSE)
        else :
            # Selector path is blocked
            self.gcode.respond_info(
                "Selector path is blocked, "
                " please check the ERCF, calling %s..."
                % self.MACRO_PAUSE)
            self.gcode.run_script_from_command(self.MACRO_UNSELECT_TOOL)
            self.gcode.run_script_from_command(self.MACRO_PAUSE)

    cmd_ERCF_ENDLESSSPOOL_UNLOAD_help = "Unload the filament from the toolhead"
    def cmd_ERCF_ENDLESSSPOOL_UNLOAD(self, gcmd):
        self.gcode.respond_info("This is a placeholder")

    cmd_ERCF_FINALIZE_LOAD_help = "Finalize the load of a tool to the nozzle"
    def cmd_ERCF_FINALIZE_LOAD(self, gcmd):
        length = gcmd.get_float('LENGTH', None, above=0.)
        if length is None :
            self.gcode.respond_info("LENGTH has to be specified")
            return
        self._counter.reset_counts()
        pos = self.toolhead.get_position()
        pos[3] += 15.
        self.toolhead.manual_move(pos, 30)
        pos[3] += ( length - 20. )
        self.toolhead.manual_move(pos, 30)
        pos[3] += 5.
        self.toolhead.manual_move(pos, 10)
        self.toolhead.wait_moves()
        self.toolhead.dwell(0.4)
        final_encoder_pos = self._counter.get_distance()
        if final_encoder_pos < 15. :
            self.gcode.respond_info(
                "Filament seems blocked between the extruder and the nozzle,"
                " calling %s..."
                % self.MACRO_PAUSE)
            self.gcode.run_script_from_command(self.MACRO_PAUSE)
            return
        self.gcode.respond_info("Filament loaded successfully")

def load_config(config):
    return Ercf(config)
