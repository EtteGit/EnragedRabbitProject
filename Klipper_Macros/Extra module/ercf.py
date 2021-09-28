import logging
import math
from . import pulse_counter
from . import force_move
import toolhead
import copy

class EncoderCounter:
    def __init__(self, printer, pin, sample_time, poll_time, encoder_steps):
        self._callback = None
        self._last_time = self._last_count = None
        self._counts = 0
        self._encoder_steps = encoder_steps
        self._counter = pulse_counter.MCU_counter(printer, pin, sample_time, poll_time)
        self._counter.setup_callback(self._counter_callback)

    def _counter_callback(self, time, count, count_time):
        if self._last_time is None:  # First sample
            self._last_time = time
        else:
            delta_time = count_time - self._last_time

            if delta_time > 0:
                self._last_time = count_time
                delta_count = count - self._last_count
                self._counts += delta_count
            else:  # No counts since last sample
                self._last_time = time
        self._last_count = count

    def get_counts(self):
        return self._counts

    def get_distance(self):
        return (self._counts/2.0) * self._encoder_steps

    def set_distance(self, new_distance):
        self._counts = int((new_distance/self._encoder_steps)*2.0)

    def reset_counts(self):
        self._counts = 0.

class Ercf:
    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        # Selector manual stepper
        self.selector_stepper = None
        for manual_stepper in self.printer.lookup_objects('manual_stepper'):
            if manual_stepper[1].rail.get_name() == 'manual_stepper selector_stepper':
                self.selector_stepper = manual_stepper[1]
        # Gear manual stepper
        self.gear_stepper = None
        for manual_stepper in self.printer.lookup_objects('manual_stepper'):
            if manual_stepper[1].rail.get_name() == 'manual_stepper gear_stepper':
                self.gear_stepper = manual_stepper[1]
        self.encoder_pin = config.get('encoder_pin')
        self.encoder_resolution = config.getfloat('encoder_resolution', 1.5, above=0.)
        self._counter = EncoderCounter(self.printer, self.encoder_pin, 0.1, 0.0001, self.encoder_resolution)
        self.ref_step_dist=self.gear_stepper.rail.steppers[0].get_step_dist()
        # Parameters
        self.long_moves_speed = float(config.get('long_moves_speed'))
        self.long_moves_accel = float(config.get('long_moves_accel'))
        self.short_moves_speed = float(config.get('short_moves_speed'))
        self.short_moves_accel = float(config.get('short_moves_accel'))
        if self.long_moves_speed is None:
            self.long_moves_speed = 100.0
        if self.long_moves_accel is None:
            self.long_moves_accel = 400.0
        if self.short_moves_speed is None:
            self.short_moves_speed = 25.0
        if self.short_moves_accel is None:
            self.short_moves_accel = 400.0
        # GCODE commands
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command('ERCF_CALIBRATE_ENCODER', self.cmd_ERCF_CALIBRATE_ENCODER, desc=self.cmd_ERCF_CALIBRATE_ENCODER_help)
        self.gcode.register_command('ERCF_RESET_ENCODER_COUNTS', self.cmd_ERCF_RESET_ENCODER_COUNTS, desc=self.cmd_ERCF_RESET_ENCODER_COUNTS_help)
        self.gcode.register_command('ERCF_LOAD', self.cmd_ERCF_LOAD, desc=self.cmd_ERCF_LOAD_help)
        self.gcode.register_command('ERCF_UNLOAD', self.cmd_ERCF_UNLOAD, desc=self.cmd_ERCF_UNLOAD_help)
        self.gcode.register_command('ERCF_BUZZ_GEAR_MOTOR', self.cmd_ERCF_BUZZ_GEAR_MOTOR, desc=self.cmd_ERCF_BUZZ_GEAR_MOTOR_help)
        self.gcode.register_command('ERCF_HOME_EXTRUDER', self.cmd_ERCF_HOME_EXTRUDER, desc=self.cmd_ERCF_HOME_EXTRUDER_help)
        self.gcode.register_command('ERCF_SET_STEPS', self.cmd_ERCF_SET_STEPS, desc=self.cmd_ERCF_SET_STEPS_help)
        self.gcode.register_command('ERCF_GET_SELECTOR_POS', self.cmd_ERCF_GET_SELECTOR_POS, desc=self.cmd_ERCF_GET_SELECTOR_POS_help)

    def get_status(self, eventtime):
        encoder_pos = float(self._counter.get_distance())
        return {'encoder_pos': encoder_pos}

    def _sample_stats(self, values):
        mean = sum(values) / len(values) if (len(values) > 0) else 0.
        stdev = 0
        vmin = 0
        vmax = 0
        if (len(values) > 1):
            stdev = math.sqrt(sum([(v - mean)**2 for v in values])/(len(values) - 1))
        if (len(values) > 1):
            vmin = min(values)
            vmax = max(values)
        return {'mean': mean, 'stdev': stdev, 'min': vmin,
                        'max': vmax, 'range': vmax - vmin}

    def cmd_ERCF_CALIBRATE_ENCODER(self, gcmd):
        self.dist = gcmd.get_float('DIST', None)
        self.range = gcmd.get_int('RANGE', None)
        self.speed = gcmd.get_float('SPEED', None)
        self.accel = gcmd.get_float('ACCEL', None)
        if self.dist is None:
            self.dist = 500.0
        if self.speed is None:
            self.speed = 100.0
        if self.accel is None:
            self.accel = 200.0
        if self.range is None:
            self.range = 5
        self.plus_values = []
        self.minus_values = []
        self.toolhead = self.printer.lookup_object('toolhead')
        self.gear_stepper.do_set_position(0.)

        for x in range(self.range):
            self._counter.reset_counts()
            self.gear_stepper.do_move(self.dist, self.speed, self.accel, True)
            self.toolhead.wait_moves()
            self.plus_values.append(self._counter.get_counts())
            self.gcode.respond_info("+ counts =  %.3f" % (self._counter.get_counts()))

            self._counter.reset_counts()
            self.gear_stepper.do_move(0., self.speed, self.accel, True)
            self.toolhead.wait_moves()
            self.minus_values.append(self._counter.get_counts())
            self.gcode.respond_info("- counts =  %.3f" % (self._counter.get_counts()))

        gcmd.respond_info("Load direction: mean=%(mean).2f stdev=%(stdev).2f min=%(min)d max=%(max)d range=%(range)d" 
        % self._sample_stats(self.plus_values))
        gcmd.respond_info("Unload direction: mean=%(mean).2f stdev=%(stdev).2f min=%(min)d max=%(max)d range=%(range)d" 
        % self._sample_stats(self.minus_values))
        
        self.mean_plus = self._sample_stats(self.plus_values)['mean']
        self.mean_minus = self._sample_stats(self.minus_values)['mean']
        
        self.full_mean = (float(self.mean_plus) + float(self.mean_minus))/2
        self.resolution =self.dist/(self.full_mean/2)
        self.old_result = (self.full_mean/2)*self.encoder_resolution
        self.new_result = (self.full_mean/2)*self.resolution
        
        gcmd.respond_info("Before calibration measured length = %.6f" 
        % self.old_result)
        gcmd.respond_info("Resulting resolution for the encoder = %.6f" 
        % self.resolution)
        gcmd.respond_info("After calibration measured length = %.6f" 
        % self.new_result)

    cmd_ERCF_CALIBRATE_ENCODER_help = "Calibration routine for the ERCF encoder"

    def cmd_ERCF_HOME_EXTRUDER(self, gcmd):
        self.toolhead = self.printer.lookup_object('toolhead')
        self.home_length = gcmd.get_float('TOTAL_LENGTH', None)
        self.step_length = gcmd.get_float('STEP_LENGTH', None)
        self.both_in_sync = True
        if self.home_length is None:
            self.home_length = 80.0
        if self.step_length is None:
            self.step_length = 1.0
        self.home_speed = 35.0
        self.sensor = self.printer.lookup_object('filament_switch_sensor toolhead_sensor')
        sensor_state = bool(self.sensor.runout_helper.filament_present)
        if sensor_state == True:
            self.step_length = -self.step_length
            self.both_in_sync = False # Do not move the ERCF if move is an unload
        for step in range(int(self.home_length/abs(self.step_length)) + 1):
            if bool(self.sensor.runout_helper.filament_present) == sensor_state:
                if step*abs(self.step_length) >= self.home_length :
                    self.gcode.respond_info("Unable to reach the toolhead sensor")
                    self.gcode.run_script_from_command("ERCF_UNSELECT_TOOL")
                    self.gcode.run_script_from_command("ERCF_PAUSE")
                    break
                if self.both_in_sync :
                    self.gear_stepper.do_set_position(0.)
                    self.gear_stepper.do_move(self.step_length, self.home_speed, 400, False)
                pos = self.toolhead.get_position()
                pos[3] += self.step_length
                self.toolhead.manual_move(pos, self.home_speed)
                self.toolhead.dwell(0.2)
            else:
                self.gear_stepper.do_set_position(0.)
                break

    cmd_ERCF_HOME_EXTRUDER_help = "Home the filament tip on the toolhead sensor"

    def cmd_ERCF_RESET_ENCODER_COUNTS(self, gcmd):
        self._counter.reset_counts() 

    cmd_ERCF_RESET_ENCODER_COUNTS_help = "Reset the ERCF encoder counts"

    def cmd_ERCF_BUZZ_GEAR_MOTOR(self, gcmd):
        self._counter.reset_counts()
        self.gear_stepper.do_set_position(0.)
        self.gear_stepper.do_move(2, self.short_moves_speed, self.short_moves_accel, True)
        self.gear_stepper.do_move(0, self.short_moves_speed, self.short_moves_accel, True)
        self.toolhead = self.printer.lookup_object('toolhead')
        self.toolhead.wait_moves()

    cmd_ERCF_BUZZ_GEAR_MOTOR_help = "Buzz the ERCF gear motor"

    def cmd_ERCF_LOAD(self, gcmd):
        self.move_length = gcmd.get_float('LENGTH', None)
        self.iterate = True
        if self.move_length is None:
            self.move_length = 0.0
            self.iterate = False
        self._counter.reset_counts() 
        self.gear_stepper.do_set_position(0.)
        self.gear_stepper.do_move(70.0, self.short_moves_speed, self.short_moves_accel, True)
        self.toolhead = self.printer.lookup_object('toolhead')
        self.toolhead.wait_moves()
        self.gear_stepper.do_set_position(0.)

        if self._counter.get_distance() <= 6.0:
            self.gcode.respond_info("Error loading filament to ERCF, no filament detected during load sequence, retry loading...")
            self.gcode.run_script_from_command("ERCF_SERVO_UP")
            self.gcode.run_script_from_command("ERCF_SERVO_DOWN")
            self.gear_stepper.do_move(70.0, self.short_moves_speed, self.short_moves_accel, True)
            self.toolhead = self.printer.lookup_object('toolhead')
            self.toolhead.wait_moves()
            self.gear_stepper.do_set_position(0.)
            if self._counter.get_distance() <= 6.0:
                self.gcode.respond_info("Still no filament loaded in the ERCF, calling ERCF_PAUSE...")
                self.gcode.run_script_from_command("ERCF_UNSELECT_TOOL")
                self.gcode.run_script_from_command("ERCF_PAUSE")
                return
            else :
                self.gcode.respond_info("Filament loaded in ERCF")
        
        if self.move_length != 0:
            self.gear_stepper.do_move(self.move_length - self._counter.get_distance(), self.long_moves_speed, self.long_moves_accel, True)
            self.toolhead.wait_moves()
            self.gcode.respond_info("Load move done, requested = %.1f, measured = %.1f"
            %(self.move_length, self._counter.get_distance()))
            if (self.move_length - self._counter.get_distance()) > 4.0 and self.iterate == True:
                self.gear_stepper.do_set_position(0.)
                if (self.move_length - self._counter.get_distance()) > 60.0 :
                    self.gear_stepper.do_move(self.move_length - self._counter.get_distance(), self.long_moves_speed, self.long_moves_speed, True)
                else :
                    self.gear_stepper.do_move(self.move_length - self._counter.get_distance(), self.short_moves_speed, self.short_moves_accel, True)
                self.toolhead.wait_moves()
                self.gcode.respond_info("Correction load move done, requested = %.1f, measured = %.1f"
                %(self.move_length, self._counter.get_distance()))
                if (self.move_length - self._counter.get_distance()) > 4.0 :
                    if (self.move_length - self._counter.get_distance()) <= 60.0 :
                        self.gear_stepper.do_set_position(0.)
                        self.gear_stepper.do_move(self.move_length - self._counter.get_distance(), self.short_moves_speed, self.short_moves_accel, True)
                        self.toolhead.wait_moves()
                        self.gcode.respond_info("Correction load move done, requested = %.1f, measured = %.1f"
                        %(self.move_length, self._counter.get_distance()))
                    else :
                        self.gcode.respond_info("Too much slippage detected during the load, please check the ERCF, calling ERCF_PAUSE...")
                        self.gcode.run_script_from_command("ERCF_UNSELECT_TOOL")
                        self.gcode.run_script_from_command("ERCF_PAUSE")

    cmd_ERCF_LOAD_help = "Load filament from ERCF to the toolhead"

    def cmd_ERCF_UNLOAD(self, gcmd):
        # Define unload move parameters
        self.iterate = True
        self.home_speed = 80.0
        self.home_accel = 400.0
        self.buffer_length = 45.0
        self.homing_move = gcmd.get_int('HOMING', None)
        self.move_length = gcmd.get_float('LENGTH', 1200.0)
        self.toolhead = self.printer.lookup_object('toolhead')
        self.toolhead.wait_moves()
        
        if self.homing_move is None:
            self.homing_move = 0
        if self.move_length >= 90.0: # i.e. long move that will be fast and iterated using the encoder
            self.move_speed = self.long_moves_speed
            self.move_accel = self.long_moves_accel
            self.move_length = self.move_length - self.buffer_length
        else:
            self.move_speed = self.short_moves_speed
            self.move_accel = self.short_moves_accel
            self.iterate = False
        
        # Do the unload move
        self.gear_stepper.do_set_position(0.)

        if self.homing_move == 1:
            self.iterate = False
            self._counter.reset_counts()
            for step in range(int(self.move_length/15.0)):
                self._counter.reset_counts()
                self.gear_stepper.do_set_position(0.)
                self.gear_stepper.do_move(-15.0, self.move_speed, self.move_accel, True)
                self.toolhead.wait_moves()
                
                self.delta = 15.0 - self._counter.get_distance()
                
                if self.delta >= 3.0 :
                    self._counter.reset_counts()
                    self.gear_stepper.do_set_position(0.)
                    self.gear_stepper.do_move(-(23.0 - self.delta), self.move_speed, self.move_accel, True)
                    self.toolhead.wait_moves()
                    
                    if self._counter.reset_counts() < 5.0 :
                        return
        else:
            self._counter.reset_counts()
            self.gear_stepper.do_move(-self.move_length, self.move_speed, self.move_accel, True)
            
        self.toolhead.wait_moves()
        self.gear_stepper.do_set_position(0.)
        
        if self.iterate == True:
            self.gcode.respond_info("Unload move done, requested = %.1f, measured = %.1f"
            %(self.move_length, self._counter.get_distance()))
            
            self.delta_length = self.move_length - self._counter.get_distance()
            if self.delta_length >= 3.5:
                self.gear_stepper.do_set_position(0.)
                self.gear_stepper.do_move(-(self.delta_length), self.short_moves_speed, self.short_moves_accel, True)
                self.toolhead.wait_moves()
                
                self.gcode.respond_info("Correction unload move done, requested = %.1f, measured = %.1f"
                %(self.move_length, self._counter.get_distance()))
            
            # Final move to park position
            self.gear_stepper.do_set_position(0.)
            self.gear_stepper.do_move(-(self.buffer_length), self.short_moves_speed, self.short_moves_accel, True)
            self.toolhead.wait_moves()

    cmd_ERCF_UNLOAD_help = "Unload filament and park it in the ERCF"

    def cmd_ERCF_SET_STEPS(self, gcmd):
        self._ratio = gcmd.get_float('RATIO', 1.0)
        self.new_step_dist = self.ref_step_dist/self._ratio
        self.gear_stepper.rail.steppers[0].set_step_dist(self.new_step_dist)
    
    cmd_ERCF_SET_STEPS_help = "Changes the steps/mm for the ERCF gear motor"
    
    def cmd_ERCF_GET_SELECTOR_POS(self, gcmd):
        self.ref_pos = gcmd.get_float('REF', 0.0)
        self.selector_stepper.do_set_position(0.)
        self._init_position = self.selector_stepper.steppers[0].get_mcu_position()
        
        self.command_string = ("MANUAL_STEPPER STEPPER=selector_stepper SPEED=20 MOVE=-" + str(self.ref_pos) + " STOP_ON_ENDSTOP=1")
        self.gcode.run_script_from_command(self.command_string)
  
        self._current_position = self.selector_stepper.steppers[0].get_mcu_position()
        self.traveled_position = abs(self._current_position - self._init_position) * self.selector_stepper.steppers[0].get_step_dist()
        
        self.gcode.respond_info("Selector position = %.1f "
        %(self.traveled_position))
    
    cmd_ERCF_GET_SELECTOR_POS_help = "Report the selector motor position"
    
def load_config(config):
    return Ercf(config)