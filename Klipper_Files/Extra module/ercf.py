# Enraged Rabbit Carrot Feeder
#
# Copyright (C) 2021  Ette
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
import math
from random import randint
from . import pulse_counter
from . import force_move
import copy
import time

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
    SERVO_DOWN_STATE = 1
    SERVO_UP_STATE = 0
    SERVO_UNKNOWN_STATE = -1

    LOADED_STATUS_UNKNOWN = -1
    LOADED_STATUS_UNLOADED = 0
    LOADED_STATUS_PARTIAL = 1
    LOADED_STATUS_FULL = 2

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
        self.encoder_sample_time = config.getfloat('encoder_sample_time', 0.1,
                                            above=0.)
        self.encoder_poll_time = config.getfloat('encoder_poll_time', 0.0001,
                                            above=0.)
        self._counter = EncoderCounter(self.printer, self.encoder_pin, 
                                            self.encoder_sample_time,
                                            self.encoder_poll_time, 
                                            self.encoder_resolution)
        
        # Parameters
        self.long_moves_speed = config.getfloat('long_moves_speed', 100.)
        self.long_moves_accel = config.getfloat('long_moves_accel', 400.)
        self.short_moves_speed = config.getfloat('short_moves_speed', 25.)
        self.short_moves_accel = config.getfloat('short_moves_accel', 400.)
        self.log_level = config.getint('log_level', 1)
        self.gear_stepper_accel = config.getint('gear_stepper_accel', 0)
        self.servo_down_angle = config.getfloat('servo_down_angle')
        self.servo_up_angle = config.getfloat('servo_up_angle')
        self.extra_servo_dwell_down = config.getint('extra_servo_dwell_down', 0)
        self.extra_servo_dwell_up = config.getint('extra_servo_dwell_up', 0)
        self.end_of_bowden_to_nozzle = config.getfloat('end_of_bowden_to_nozzle', above=30.)
        self.num_moves = config.getint('num_moves', 2)
        self.parking_distance = config.getfloat('parking_distance', 23., above=15., below=30.)
        self.encoder_move_step_size = config.getfloat('encoder_move_step_size', 15., above=5., below=25.)
        self.selector_offsets = config.getfloatlist('colorselector')
        self.timeout_pause = config.getint('timeout_pause', 72000)
        self.disable_heater = config.getint('disable_heater', 600)
        self.log_statistics = config.getint('log_statistics', 0)
        self.min_temp_extruder = config.getfloat('min_temp_extruder', 180.)
        self.calibration_bowden_length = config.getfloat('calibration_bowden_length')
        self.unload_buffer = config.getfloat('unload_buffer', 30.)
        self.sync_unload_length = config.getfloat('sync_unload_length', 20.)
        self.unload_parking_position = config.getfloat('unload_parking_position', 0.)
        self.extruder_homing_max = config.getfloat('extruder_homing_max', 50.)
        self.extruder_homing_step = config.getfloat('extruder_homing_step', 2.)
        self.sensorless_selector = config.getint('sensorless_selector', 0)
        self.enable_clog_detection = config.getint('enable_clog_detection', 1)
        self.enable_endless_spool = config.getint('enable_endless_spool', 0)
        self.endless_spool_groups = config.getintlist('endless_spool_groups')

        if self.enable_endless_spool == 1 and len(self.endless_spool_groups) != len(self.selector_offsets):
            raise config.error(
                "EndlessSpool mode requires that the endless_spool_groups parameter is set with the same number of values as the number of selectors")



        # State variables
        self.is_paused = False
        self.paused_extruder_temp = 0.
        self.is_homed = False
        self.tool_selected = -1
        self.servo_state = self.SERVO_UNKNOWN_STATE
        self.loaded_status = self.LOADED_STATUS_UNKNOWN

        # Statistics
        self.total_swaps = 0
        self.time_spent_loading = 0
        self.time_spent_unloading = 0
        self.time_spent_paused = 0
        self.total_pauses = 0

        # GCODE commands
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command('ERCF_CALIBRATE_ENCODER',
                    self.cmd_ERCF_CALIBRATE_ENCODER,
                    desc=self.cmd_ERCF_CALIBRATE_ENCODER_help)
        self.gcode.register_command('ERCF_LOAD',
                    self.cmd_ERCF_LOAD,
                    desc=self.cmd_ERCF_LOAD_help)
        self.gcode.register_command('ERCF_UNLOAD',
                    self.cmd_ERCF_UNLOAD,
                    desc=self.cmd_ERCF_UNLOAD_help)
        self.gcode.register_command('ERCF_BUZZ_GEAR_MOTOR',
                    self.cmd_ERCF_BUZZ_GEAR_MOTOR,
                    desc=self.cmd_ERCF_BUZZ_GEAR_MOTOR_help)
        self.gcode.register_command('ERCF_SET_LOG_LEVEL',
                    self.cmd_ERCF_SET_LOG_LEVEL,
                    desc = self.cmd_ERCF_SET_LOG_LEVEL_help)
        self.gcode.register_command('ERCF_SERVO_DOWN',
                    self.cmd_ERCF_SERVO_DOWN,
                    desc = self.cmd_ERCF_SERVO_DOWN_help)                       
        self.gcode.register_command('ERCF_SERVO_UP',
                    self.cmd_ERCF_SERVO_UP,
                    desc = self.cmd_ERCF_SERVO_UP_help)
        self.gcode.register_command('ERCF_TEST_SERVO',
                    self.cmd_ERCF_TEST_SERVO,
                    desc = self.cmd_ERCF_TEST_SERVO_help)                          
        self.gcode.register_command('ERCF_MOTORS_OFF',
                    self.cmd_ERCF_MOTORS_OFF,
                    desc = self.cmd_ERCF_MOTORS_OFF_help)
        self.gcode.register_command('ERCF_CHANGE_TOOL_SLICER',
                    self.cmd_ERCF_CHANGE_TOOL_SLICER,
                    desc = self.cmd_ERCF_CHANGE_TOOL_SLICER_help)
        self.gcode.register_command('ERCF_CHANGE_TOOL',
                    self.cmd_ERCF_CHANGE_TOOL,
                    desc = self.cmd_ERCF_CHANGE_TOOL_help)
        self.gcode.register_command('ERCF_CHANGE_TOOL_STANDALONE',
                    self.cmd_ERCF_CHANGE_TOOL_STANDALONE,
                    desc = self.cmd_ERCF_CHANGE_TOOL_STANDALONE_help)
        self.gcode.register_command('ERCF_HOME',
                    self.cmd_ERCF_HOME,
                    desc = self.cmd_ERCF_HOME_help)
        self.gcode.register_command('ERCF_PAUSE',
                    self.cmd_ERCF_PAUSE,
                    desc = self.cmd_ERCF_PAUSE_help)
        self.gcode.register_command('ERCF_UNLOCK',
                    self.cmd_ERCF_UNLOCK,
                    desc = self.cmd_ERCF_HOME_help)
        self.gcode.register_command('ERCF_EJECT',
                    self.cmd_ERCF_EJECT,
                    desc = self.cmd_ERCF_EJECT_help)
        self.gcode.register_command('ERCF_RESET_STATS',
                    self.cmd_ERCF_RESET_STATS,
                    desc = self.cmd_ERCF_RESET_STATS_help)
        self.gcode.register_command('ERCF_DUMP_STATS',
                    self.cmd_ERCF_DUMP_STATS,
                    desc = self.cmd_ERCF_DUMP_STATS_help)
        self.gcode.register_command('ERCF_CALIBRATE',
                    self.cmd_ERCF_CALIBRATE,
                    desc = self.cmd_ERCF_CALIBRATE_help)
        self.gcode.register_command('ERCF_CALIBRATE_SINGLE',
                    self.cmd_ERCF_CALIBRATE_SINGLE,
                    desc = self.cmd_ERCF_CALIBRATE_SINGLE_help)
        self.gcode.register_command('ERCF_CALIB_SELECTOR',
                    self.cmd_ERCF_CALIB_SELECTOR,
                    desc = self.cmd_ERCF_CALIB_SELECTOR_help)     
        self.gcode.register_command('ERCF_ENCODER_RUNOUT', 
                    self.cmd_ERCF_ENCODER_RUNOUT,
                    desc = self.cmd_ERCF_ENCODER_RUNOUT_help)
        self.gcode.register_command('ERCF_DISPLAY_ENCODER_POS', 
                    self.cmd_ERCF_DISPLAY_ENCODER_POS,
                    desc = self.cmd_ERCF_DISPLAY_ENCODER_POS_help)                    
        self.gcode.register_command('ERCF_TEST_GRIP', 
                    self.cmd_ERCF_TEST_GRIP,
                    desc = self.cmd_ERCF_TEST_GRIP_help)      
        self.gcode.register_command('ERCF_TEST_MOVE_GEAR',
                    self.cmd_ERCF_TEST_MOVE_GEAR,
                    desc = self.cmd_ERCF_TEST_MOVE_GEAR_help)
        self.gcode.register_command('ERCF_TEST_LOAD_SEQUENCE',
                    self.cmd_ERCF_TEST_LOAD_SEQUENCE,
                    desc = self.cmd_ERCF_TEST_LOAD_SEQUENCE_help)
        self.gcode.register_command('ERCF_SET_END_OF_BOWDEN_TO_NOZZLE',
                    self.cmd_ERCF_SET_END_OF_BOWDEN_TO_NOZZLE,
                    desc = self.cmd_ERCF_SET_END_OF_BOWDEN_TO_NOZZLE_help)                    
        self.gcode.register_command('ERCF_SELECT_TOOL',
                    self.cmd_ERCF_SELECT_TOOL,
                    desc = self.cmd_ERCF_SELECT_TOOL_help)    

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
        self.variables = self.printer.lookup_object('save_variables').allVariables
        self.encoder_sensor = self.printer.lookup_object("filament_motion_sensor encoder_sensor")
        self.printer.register_event_handler("klippy:ready", self._setup_heater_off_reactor)
        self._reset_statistics()

    def get_status(self, eventtime):
        encoder_pos = float(self._counter.get_distance())
        return {'encoder_pos': encoder_pos, 'is_paused': self.is_paused, 'tool': self.tool_selected, 'clog_detection': self.enable_clog_detection}

########################
# STATISTICS FUNCTIONS #
########################
    def _reset_statistics(self):
        self.total_swaps = 0
        self.time_spent_loading = 0
        self.time_spent_unloading = 0
        self.total_pauses = 0
        self.time_spent_paused = 0

        self.tracked_start_time = 0
        self.pause_start_time = 0

    def _track_swap_completed(self):
        self.total_swaps += 1

    def _track_load_start(self):
        self.tracked_start_time = time.time()

    def _track_load_end(self):
        self.time_spent_loading += time.time() - self.tracked_start_time

    def _track_unload_start(self):
        self.tracked_start_time = time.time()

    def _track_unload_end(self):
        self.time_spent_unloading += time.time() - self.tracked_start_time

    def _track_pause_start(self):
        self.total_pauses += 1
        self.pause_start_time = time.time()

    def _track_pause_end(self):
        self.time_spent_paused += time.time() - self.pause_start_time

    def _seconds_to_human_string(self, seconds):
        result = ""
        hours = int(math.floor(seconds / 3600.))
        if hours >= 1:
            result += "%d hours " % hours
        minutes = int(math.floor(seconds / 60.) % 60)
        if hours >= 1 or minutes >= 1:
            result += "%d minutes " % minutes
        result += "%d seconds" % int((math.floor(seconds) % 60))
        return result

    def _dump_statistics(self):
        if self.log_statistics:
            self._log_info("ERCF Statistics:")
            self._log_info("%d Swaps Completed" % self.total_swaps)
            self._log_info("%s spent loading" % self._seconds_to_human_string(self.time_spent_loading))
            self._log_info("%s spent unloading" % self._seconds_to_human_string(self.time_spent_unloading))
            self._log_info("%s spent paused (%d pauses total)" % (self._seconds_to_human_string(self.time_spent_paused), self.total_pauses))

    cmd_ERCF_RESET_STATS_help = "Reset the ERCF statistics"
    def cmd_ERCF_RESET_STATS(self, gcmd):
        self._reset_statistics()

    cmd_ERCF_DUMP_STATS_help = "Dump the ERCF statistics"
    def cmd_ERCF_DUMP_STATS(self, gcmd):
        self._dump_statistics()

###################
# SERVO FUNCTIONS #
###################
    def _servo_set_angle(self, angle):
        # if we ever set the angle directly, we are in an unknown state
        # the up/down functions will reset this properly
        self.servo_state = self.SERVO_UNKNOWN_STATE 
        self.gcode.run_script_from_command("SET_SERVO SERVO=ercf_servo ANGLE=%1.f" % angle)

    def _servo_off(self):
        self.gcode.run_script_from_command("SET_SERVO SERVO=ercf_servo WIDTH=0.0")

    def _servo_down(self):
        if self.servo_state == self.SERVO_DOWN_STATE:
            return

        self._log_debug("Setting servo to down angle: %d" % (self.servo_down_angle))
        self.gear_stepper.do_set_position(0.)
        self.gear_stepper.do_move(0.5, 25, self.gear_stepper_accel, sync=0)

        self._servo_set_angle(self.servo_down_angle)

        self.toolhead.dwell(0.2)
        self.gear_stepper.do_move(0., 25, self.gear_stepper_accel, sync=0)
        self.toolhead.dwell(0.1)
        self.gear_stepper.do_move(0.5, 25, self.gear_stepper_accel, sync=0)
        self.toolhead.dwell(0.1 + self.extra_servo_dwell_down / 1000.)
        self.gear_stepper.do_move(0., 25, self.gear_stepper_accel, sync=0)

        self._servo_off()
        self.servo_state = self.SERVO_DOWN_STATE

    def _servo_up(self):
        if self.servo_state == self.SERVO_UP_STATE:
            return

        self._log_debug("Setting servo to up angle: %d" % (self.servo_up_angle))
        self._servo_set_angle(self.servo_up_angle)
        self.toolhead.dwell(0.25 + self.extra_servo_dwell_up / 1000.)
        self._servo_off()
        self.servo_state = self.SERVO_UP_STATE

    cmd_ERCF_SERVO_UP_help = "Disengage the ERCF gear"
    def cmd_ERCF_SERVO_UP(self, gcmd):
        self._servo_up()

    cmd_ERCF_SERVO_DOWN_help = "Engage the ERCF gear"
    def cmd_ERCF_SERVO_DOWN(self, gcmd):
        self._servo_down()

    cmd_ERCF_TEST_SERVO_help = "Test the servo angle"
    def cmd_ERCF_TEST_SERVO(self, gcmd):
        angle = gcmd.get_float('VALUE')

        self._servo_set_angle(angle)
        self.toolhead.dwell(0.25 + self.extra_servo_dwell_up / 1000.)
        self._servo_off()

#########################
# CALIBRATION FUNCTIONS #
#########################
    def _get_calibration_ref(self):
        return self.variables['ercf_calib_ref']

    def _get_tool_ratio(self, tool):
        if tool < 0:
            return 1.
        return self.variables['ercf_calib_%d' % tool]

    def _get_calibration_version(self):
        return self.variables.get('ercf_calib_version', 1)

    def _do_calculate_calibration_ref(self, extruder_homing_length = 400, extruder_homing_step = 2):
        # assume we are homed and unloaded
        self._select_tool(0)
        self._servo_down()
        self._set_steps(1.)
        self._set_above_min_temp()
        self._log_info("Calibrating reference tool")
        encoder_moved = self._load_into_encoder()
        self._load_to_end_of_bowden(self.calibration_bowden_length-encoder_moved)     
        if self.is_paused:
            return

        self._log_debug("Moved to calibration distance %.1f - encoder reads %.1f" % (self.calibration_bowden_length, self._counter.get_distance()))

        final_position = self._home_to_extruder(extruder_homing_length, extruder_homing_step)
        if self.is_paused:
            self._log_info("Calibration failed - unable to home to the extruder")
            return
        self._log_info("Calibration reference is %.1f" % final_position)
        self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=ercf_calib_ref VALUE=%.1f" % final_position)
        self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=ercf_calib_0 VALUE=1.0")  
        self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=ercf_calib_version VALUE=2")  
        self._do_calibration_unload(final_position)

    def _do_calculate_calibration_ratio(self, tool):
        if self.is_paused:
            return

        load_length = self.calibration_bowden_length - 100.

        self._select_tool(tool)
        self._servo_down()
        self._set_steps(1.)
        self._counter.reset_counts()
        encoder_moved = self._load_into_encoder()
        self._load_to_end_of_bowden(load_length-encoder_moved)   
        final_position = self._counter.get_distance()
        ratio = load_length / final_position
        self._log_info("Calibration move to %.1f read distance %.1f - Ratio is %.12f" % (load_length, final_position, ratio))
        self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=ercf_calib_%d VALUE=%.12f" % (tool, ratio))  
        self._do_calibration_unload(load_length)

    def _do_calibration_unload(self, length):
        self._set_steps(1.)
        self.toolhead.dwell(0.1)
        self.toolhead.wait_moves()
        self._unload_from_end_of_bowden(length-self.unload_buffer)
        self._unload_encoder(10)        
        self._servo_up()            

    cmd_ERCF_CALIBRATE_help = "Complete calibration of all ERCF Tools"
    def cmd_ERCF_CALIBRATE(self, gcmd):
        self._disable_encoder_sensor()
        self._log_info("Start the complete auto calibration...")
        self._do_home(0)
        for i in range(len(self.selector_offsets)):
            if i == 0:
                self._do_calculate_calibration_ref()
            else:
                self._do_calculate_calibration_ratio(i)
        self._log_info("End of the complete auto calibration!")
        self._log_info("Please reload the firmware for the calibration to be active!")

    cmd_ERCF_CALIBRATE_SINGLE_help = "Calibration of a single ERCF Tool"
    def cmd_ERCF_CALIBRATE_SINGLE(self, gcmd):
        tool = gcmd.get_int('TOOL', 0)
        if tool == 0:
            self._do_home(0)
            self._do_calculate_calibration_ref()
        else:
            self._do_home(tool)
            self._do_calculate_calibration_ratio(tool)

    cmd_ERCF_CALIB_SELECTOR_help = "Calibration of the selector position for a defined Tool"
    def cmd_ERCF_CALIB_SELECTOR(self, gcmd):
        self._servo_up()
        tool = gcmd.get_int('TOOL', 0, minval=0)
        move_length = 20 + (tool + 1) * 21 + ((tool + 1) / 3) * 5
        self._log_info("Measuring the selector position for tool %d" % tool)

        self.selector_stepper.do_set_position(0.)
        init_position = self.selector_stepper.steppers[0].get_mcu_position()
        self.selector_stepper.do_homing_move(-move_length, 50, self.selector_stepper.accel, True, True)
        current_position = self.selector_stepper.steppers[0].get_mcu_position()
        traveled_position = abs(current_position - init_position) * self.selector_stepper.steppers[0].get_step_dist()
        self._log_info("Selector position = %.1f" % traveled_position)

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

    cmd_ERCF_TEST_GRIP_help = "Test the ERCF grip for a Tool"
    def cmd_ERCF_TEST_GRIP(self, gcmd):
        self._servo_down()
        self.cmd_ERCF_MOTORS_OFF(gcmd)

    cmd_ERCF_TEST_MOVE_GEAR_help = "Move the ERCF gear"
    def cmd_ERCF_TEST_MOVE_GEAR(self, gcmd):
        length = gcmd.get_float('LENGTH', 200.)
        speed = gcmd.get_float('SPEED', 50.)
        accel = gcmd.get_float('ACCEL', 200.)
        self.gear_stepper.do_set_position(0.)
        self.gear_stepper.do_move(length, speed, accel)

    cmd_ERCF_TEST_LOAD_SEQUENCE_help = "Test sequence"
    def cmd_ERCF_TEST_LOAD_SEQUENCE(self, gcmd):
        loops = gcmd.get_int('LOOP', 10.)
        random = gcmd.get_int('RAND', 0)
        for l in range(loops):
            self._log_info("testing loop %d / %d" % (l, loops))
            for t in range(len(self.selector_offsets)):
                tool = t
                if random == 1:
                    tool = randint(0, len(self.selector_offsets)-1)
                self._log_info("testing tool %d / %d" % (tool, len(self.selector_offsets)))
                self._select_tool(tool)

                self._do_load(100, True)
                self.toolhead.dwell(0.05)
                self._do_unload(100, skip_extruder=True)
                self._unselect_tool()
                self.toolhead.dwell(0.2)

###################
# STATE FUNCTIONS #
###################
    def _setup_heater_off_reactor(self):
        self.reactor = self.printer.get_reactor()
        self.heater_off_handler = self.reactor.register_timer(self._handle_pause_timeout, self.reactor.NEVER)

    def _handle_pause_timeout(self, eventtime):
        self._log_info("Disable extruder heater")
        self.gcode.run_script_from_command("M104 S0")
        return self.reactor.NEVER

    def _pause(self):
        self._track_pause_start()
        self.paused_extruder_temp = self.printer.lookup_object("extruder").heater.target_temp
        self._servo_up()
        self.is_paused = True
        self.gcode.run_script_from_command("SET_IDLE_TIMEOUT TIMEOUT=%d" % self.timeout_pause)
        self.reactor.update_timer(self.heater_off_handler, self.reactor.monotonic() + self.disable_heater)
        self._log_info("An issue with the ERCF has been detected and the ERCF has been PAUSED")
        self._log_info("When you intervene to fix the issue, first call the \"ERCF_UNLOCK\" Gcode")
        self._log_info("Refer to the manual before resuming the print")
        self.gcode.run_script_from_command("SAVE_GCODE_STATE NAME=ERCF_state")
        self._disable_encoder_sensor()
        self.gcode.run_script_from_command("PAUSE")

    def _unlock(self):
        self.is_paused = False
        self.reactor.update_timer(self.heater_off_handler, self.reactor.NEVER)
        self.gcode.run_script_from_command("M104 S%.1f" % self.paused_extruder_temp)
        self._unselect_tool()
        self.gcode.run_script_from_command("RESTORE_GCODE_STATE NAME=ERCF_state")
        self._counter.reset_counts()
        self._track_pause_end()

    def _disable_encoder_sensor(self):
        self._log_trace("Disable encoder sensor")
        self.gcode.run_script_from_command("SET_FILAMENT_SENSOR SENSOR=encoder_sensor ENABLE=0")

    def _enable_encoder_sensor(self):
        self._log_trace("Enable encoder sensor")
        self.gcode.run_script_from_command("SET_FILAMENT_SENSOR SENSOR=encoder_sensor ENABLE=1")

    def _is_in_print(self):
        return self.printer.lookup_object('idle_timeout').state == "Printing"

    def _set_above_min_temp(self):
        if not self.printer.lookup_object("extruder").heater.can_extrude :
            self._log_info("M118 Heating extruder above min extrusion temp (%.1f)" % self.min_temp_extruder)
            self.gcode.run_script_from_command("M109 S%.1f" % self.min_temp_extruder)

    cmd_ERCF_MOTORS_OFF_help = "Turn off both ERCF motors"
    def cmd_ERCF_MOTORS_OFF(self, gcmd):
        self.gear_stepper.do_enable(False)
        self.selector_stepper.do_enable(False)
        self.is_homed = False
        self.tool_selected = -1

    def _do_buzz_gear_motor(self):
        self._counter.reset_counts()
        self._gear_stepper_move_wait(2., False)
        self._gear_stepper_move_wait(-2.)        

    cmd_ERCF_BUZZ_GEAR_MOTOR_help = "Buzz the ERCF gear motor"
    def cmd_ERCF_BUZZ_GEAR_MOTOR(self, gcmd):
        self._do_buzz_gear_motor()

    cmd_ERCF_PAUSE_help = "Pause the current print and lock the ERCF operations"
    def cmd_ERCF_PAUSE(self, gcmd):
        self._pause()

    cmd_ERCF_UNLOCK_help = "Unlock ERCF operations"
    def cmd_ERCF_UNLOCK(self, gcmd):        
        self._log_info("Unlock the ERCF")
        self._unlock()
        self._log_info("Refer to the manual before resuming the print")

    cmd_ERCF_DISPLAY_ENCODER_POS_help = "Display current value of the ERCF encoder"
    def cmd_ERCF_DISPLAY_ENCODER_POS(self, gcmd):
        self._log_info("Encoder value is %.2f" % self._counter.get_distance())

    cmd_ERCF_SET_END_OF_BOWDEN_TO_NOZZLE_help = "Update the end_of_bowden_to_nozzle value"
    def cmd_ERCF_SET_END_OF_BOWDEN_TO_NOZZLE(self, gcmd):
        val = gcmd.get_float('VALUE', minval=30.)
        self.end_of_bowden_to_nozzle = val

#########################
# GENERAL MOTOR HELPERS #
#########################
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

####################
# UNLOAD FUNCTIONS #
####################
    def _check_filament_in_extruder(self, move_size = 20, threshold = 1):
        self._servo_up()
        self._log_debug("Checking for filament in extruder")
        # reset the counter and move the extruder backwards by move_size
        self._counter.reset_counts()
        pos = self.toolhead.get_position()
        pos[3] -= move_size
        self.toolhead.manual_move(pos, 20)
        self.toolhead.wait_moves()

        #check the new encoder position
        final_encoder_pos = self._counter.get_distance()
        self._log_trace("Extruder Moved %.2f, Read %.2f, Threshold %.2f" % (move_size, final_encoder_pos, threshold))

        #if the new encoder position is beyond the threshold, the filament moved
        if final_encoder_pos > threshold:
            self._log_debug("Filament found in extruder")
            return True
        else:
            self._log_debug("No filament found in extruder")
            return False

    def _check_filament_in_encoder(self):
        self._log_debug("Checking for filament in encoder")
        self._servo_down()
        self._do_buzz_gear_motor()
        final_encoder_pos = self._counter.get_distance()
        self._log_trace("After buzzing gear motor, encoder read %.1f" % final_encoder_pos)
        self._servo_up()
        return final_encoder_pos > 0.

    def _unload_from_extruder(self):
        if (self.is_paused):
            self._log_info('ERCF is currently paused.  Please use ERCF_UNLOCK')
            return
        # assume there is filament in the extruder, but a tip is already formed
        # extract the filament using the provided values, and then test that the
        # filament is actually out

        self._log_debug("Extracting filament from extruder")
        pos = self.toolhead.get_position()
        
        # initial slow move
        pos[3] -= 10
        self._log_trace("Extracting - slow move")
        self.toolhead.manual_move(pos, 12)
        self.toolhead.wait_moves()

        # faster complete move + the previous 10mm to make sure we are out
        pos[3] -= self.end_of_bowden_to_nozzle + self.unload_parking_position
        self._log_trace("Extracting - full move")
        self.toolhead.manual_move(pos, 20)
        self.toolhead.wait_moves()

        # back up 15mm at a time until the encoder doesnt see any movement
        # try this 3 times, and then give up
        out_of_extruder = False
        for i in range(3):
            self._log_debug("Testing if filament is still in the extruder - #%d" % i)
            self._counter.reset_counts()
            pos[3] -= self.encoder_move_step_size
            self.toolhead.manual_move(pos, 20)
            self.toolhead.wait_moves()
            moved_length = self._counter.get_distance()
            self._log_trace("Test extruder move of %1.fmm recorded %1.fmm at the extruder" % (self.encoder_move_step_size, moved_length))
            if (moved_length <= 1.):
                out_of_extruder = True
                break

        if out_of_extruder:
            self.loaded_status = self.LOADED_STATUS_PARTIAL
            self._log_debug("Filament is out of extruder")
        else:
            self._log_info("Filament seems to be stuck in the extruder - PAUSING")
            self._pause()

    def _unload_encoder(self, max_steps=5):
        if (self.is_paused):
            self._log_info('ERCF is currently paused.  Please use ERCF_UNLOCK')
            return

        self._servo_down()

        self._log_debug("Unloading from the encoder")
        for step in range(max_steps):
            self._counter.reset_counts()
            self._gear_stepper_move_wait(-self.encoder_move_step_size)
            dist_moved = self._counter.get_distance()
            delta = self.encoder_move_step_size - dist_moved
            self._log_trace("Unloading from encoder - step %d.  Moved %.1f, encoder read %.1f (delta %.1f)" % (step, self.encoder_move_step_size, dist_moved, delta))
            if delta >= 3.0:
                # if there is a large delta here, we are out of the encoder
                self.loaded_status = self.LOADED_STATUS_UNLOADED
                self._counter.reset_counts()
                self._gear_stepper_move_wait(-(self.parking_distance - delta))
                if self._counter.get_distance() < 5.0:
                    self._servo_up()
                    return
        self._log_info(
            "Unable to get the filament out of the encoder cart,"
            " please check the ERCF, calling ERCF_PAUSE...")
        self._pause()
            
    def _unload_from_end_of_bowden(self, length):
        if (self.is_paused):
            self._log_info('ERCF is currently paused.  Please use ERCF_UNLOCK')
            return

        # assume there is filament at the end of the bowden
        self._log_debug("Unloading from end of bowden")
        
        self._servo_down()
        self.toolhead.dwell(0.2)        
        self.toolhead.wait_moves()

        self._counter.reset_counts()
        
        # Initial unload in sync (ERCF + extruder) for xx mms
        #self._log_trace("Moving the gear and extruder motors in sync %.1f" % self.sync_unload_length) 
        #pos = self.toolhead.get_position()
        #pos[3] -= self.sync_unload_length
        #self.gear_stepper.do_move(-self.sync_unload_length, 30, self.gear_stepper_accel, sync=0)
        #self.toolhead.manual_move(pos, 30)
        #self.toolhead.wait_moves()        
        #counter_distance = self._counter.get_distance()
        #length -= counter_distance
        #self._log_debug("Sync unload move done %.1f / %.1f (diff: %.1f)" % (counter_distance, self.sync_unload_length, counter_distance - self.sync_unload_length))
        
        self._counter.reset_counts()        
        # initial attempt to unload the filament
        for i in range(self.num_moves):
            self._log_trace("Moving the gear motor %.1f" % (-length / self.num_moves))
            self._gear_stepper_move_wait(-length / self.num_moves)
        counter_distance = self._counter.get_distance()
        delta_length = length - counter_distance
        self._log_info("Unload move done: %.1f / %.1f (diff: %.1f)"
                    % (counter_distance, length, delta_length) )

        # correction attempt to unload the filament
        if delta_length >= 3.0:
            self._log_debug("Attempting a correction move of %.1f" % delta_length)
            self._gear_stepper_move_wait(-delta_length)
            counter_distance = self._counter.get_distance()
            delta_length = length - counter_distance
            self._log_info("Correction unload move done: %.1f / %.1f (diff: %.1f)"
                    % (counter_distance, length, delta_length) )

        # after correction, still too far away - abort
        if delta_length > 15.0:
            self._log_info("Too much slippage detected during the unload: %.1f / %.1f (diff: %.1f)"
                % (counter_distance, length, delta_length))
            self._pause()
            return

    def _do_unload(self, length, slow_extract=False, skip_extruder=False):
        if (self.is_paused):
            self._log_info('ERCF is currently paused.  Please use ERCF_UNLOCK')
            return

        self._track_unload_start()

        if slow_extract:
            if self._check_filament_in_encoder():
                # if we are doing a slow extract, always form a tip before any moves
                # this may be a waste if there is no filament in the extruder
                # but checking for filament before tip forming will cause stringing
                self._set_above_min_temp()
                self.gcode.run_script_from_command("_ERCF_FORM_TIP_STANDALONE")
                if self._check_filament_in_extruder():
                    #if we are in a slow extract state, check to see if filament
                    #is in the extruder. If so, we can do a fast extract instead
                    slow_extract = False
            else :
                #if we are in the slow extract state, and there is no filament in
                #the encoder, we are already ejected
                self._log_debug("Filament already ejected!")
                self._track_unload_end()
                return

        if slow_extract:
            # if we are still in slow extract mode (AKA, we know the filament
            # is not in the extruder), do a slow extract from the encoder
            self._unload_encoder(int(length / self.encoder_move_step_size) + 5)
        else:
            # fast extract means we know we are in the extruder
            # we can now do an extruder extract follow by a full bowden
            # unload and an encoder unload
            if not skip_extruder:
                self._unload_from_extruder()
            self._unload_from_end_of_bowden(length-self.unload_buffer)
            self._unload_encoder(10)
        self.loaded_status = self.LOADED_STATUS_UNLOADED
        self._track_unload_end()


    cmd_ERCF_UNLOAD_help = "Unload filament and park it in the ERCF"
    def cmd_ERCF_UNLOAD(self, gcmd):
        if (self.is_paused):
            self._log_info('ERCF is currently paused.  Please use ERCF_UNLOCK')
            return

        unknown_state = gcmd.get_int('UNKNOWN', 0, minval=0, maxval=1)
        length = gcmd.get_float('LENGTH', self._get_calibration_ref())
        self._do_unload(length, unknown_state)

    cmd_ERCF_EJECT_help = "Eject filament from the ERCF"
    def cmd_ERCF_EJECT(self, gcmd):
        if (self.is_paused):
            self._log_info('ERCF is currently paused.  Please use ERCF_UNLOCK')
            return
        self._disable_encoder_sensor()
        self._do_unload(self._get_calibration_ref(), True)

    def _do_unload_tool(self):
        self._log_info('Unload tool %d' % self.tool_selected)
        self._set_steps(self._get_tool_ratio(self.tool_selected))
        self.toolhead.dwell(0.1)
        self.toolhead.wait_moves()
        self._do_unload(self._get_calibration_ref())
        self._servo_up()        

##################
# LOAD FUNCTIONS #
##################
    def _load_into_encoder(self):
        if (self.is_paused):
            return 0

        self._servo_down()

        self._counter.reset_counts()        
        self._gear_stepper_move_wait(self.LONG_MOVE_THRESHOLD)
        self._log_trace("Initial load into encoder of %.1fmm - read %.1f on encoder" % (self.LONG_MOVE_THRESHOLD, self._counter.get_distance()))
        if self._counter.get_distance() > 6.:
            return self._counter.get_distance()
        
        self._log_info("Error loading filament - not enough detected at encoder")
        
        self._servo_up()            
        self.toolhead.wait_moves()
        self._servo_down()
        self.toolhead.wait_moves()
        self._gear_stepper_move_wait(self.LONG_MOVE_THRESHOLD)
        self._log_trace("Retry load into encoder of %.1fmm - read %.1f on encoder" % (self.LONG_MOVE_THRESHOLD, self._counter.get_distance()))
        if self._counter.get_distance() <= 6.:
            self._log_info("Error loading filament - not enough detected at encoder after retry")
            self._pause()
            return 0
        self.loaded_status = self.LOADED_STATUS_PARTIAL
        return self._counter.get_distance()
    
    def _load_to_end_of_bowden(self, length):
        if (self.is_paused):
            return

        self._servo_down()

        start_distance = self._counter.get_distance()
        for i in range(self.num_moves):
            self._gear_stepper_move_wait(length/self.num_moves)
        counter_distance = self._counter.get_distance() - start_distance
        delta_length = length - counter_distance
        self._log_info("Load move done: %.1f / %.1f (diff: %.1f)"
                    % (counter_distance, length, delta_length) )

        # correction attempt to unload the filament
        for i in range(2):
            if delta_length >= 6.0:
                self._log_debug("Attempting a correction move of %.1f" % delta_length)
                self._gear_stepper_move_wait(delta_length)
                counter_distance = self._counter.get_distance() - start_distance
                delta_length = length - counter_distance
                self._log_info("Correction load move done: %.1f / %.1f (diff: %.1f)"
                        % (counter_distance, length, delta_length) )
            else:
                break

        self.loaded_status = self.LOADED_STATUS_PARTIAL

        # after correction, still too far away - abort
        if delta_length > self.LONG_MOVE_THRESHOLD:
            self._log_info("Too much slippage detected during the load: %.1f / %.1f (diff: %.1f)"
                % (counter_distance, length, delta_length))
            self._pause()
            return

    def _home_to_extruder(self, length, step):
        self._servo_down()

        self._log_debug("Homing to extruder with %1.fmm moves" % (step))
        self.gear_stepper.do_set_position(0.)
        for i in range (int(length / step)):
            pre_move_position = self._counter.get_distance()
            self.gear_stepper.do_move(step*(i+1), 5, self.gear_stepper_accel)
            self.toolhead.dwell(0.2)
            self.toolhead.wait_moves()
            post_move_position = self._counter.get_distance()

            self._log_trace("Step #%d: pos: %.1f, last delta: %.1f" % (i, post_move_position, post_move_position - pre_move_position))
            if post_move_position - pre_move_position < step / 2.:
                # not enough movements means we've hit the extruder
                self._log_debug("Extruder reached after %d moves" % i)                
                return pre_move_position

        self._log_info("Failed to reach extruder after moving %.1fmm, pausing" % length)
        self._pause()

    def _load_to_nozzle(self):
        if (self.is_paused):
            return

        self._log_debug("Loading to the nozzle")

        self._servo_up()      
        self._counter.reset_counts()    
        pos = self.toolhead.get_position()
        pos[3] += self.end_of_bowden_to_nozzle
        self.toolhead.manual_move(pos, 20)
        self.toolhead.dwell(0.2)
        self.toolhead.wait_moves()
        moved_length = self._counter.get_distance()
        self._log_debug("Extruder move to nozzle attempted %.1f - encoder read %.1f" % (self.end_of_bowden_to_nozzle, moved_length))

        if moved_length < 5.:
            self._log_info("Move to nozzle failed, pausing!")
            self._pause()
            return

        self.loaded_status = self.LOADED_STATUS_FULL
        self._log_info('ERCF load successful')

    def _do_load(self, length, no_nozzle = False):
        if self.is_paused:
            self._log_info('ERCF is currently paused.  Please use ERCF_UNLOCK')
            return

        self._track_load_start()
        self.toolhead.wait_moves()
        already_loaded = self._load_into_encoder()
        self._load_to_end_of_bowden(length-already_loaded)        
        self._home_to_extruder(self.extruder_homing_max, self.extruder_homing_step)
        if not no_nozzle:
            self._load_to_nozzle()
        self._track_load_end()

    cmd_ERCF_LOAD_help = "Load filament from ERCF to the toolhead"
    def cmd_ERCF_LOAD(self, gcmd):
        length = gcmd.get_float('LENGTH', 100.)
        self._do_load(length, True)        

    def _do_load_tool(self, tool):
        self._log_info('Loading tool %d' % tool)
        self._set_steps(self._get_tool_ratio(tool))
        self._select_tool(tool)
        self._do_load(self._get_calibration_ref())

############################
# TOOL SELECTION FUNCTIONS #
############################
    def _do_move_selector_sensorless(self, target):
        selector_steps = self.selector_stepper.steppers[0].get_step_dist()
        init_position = self.selector_stepper.get_position()[0]
        init_mcu_pos = self.selector_stepper.steppers[0].get_mcu_position()
        target_move = target - init_position
        self._selector_stepper_move_wait(target, 2)
        mcu_position = self.selector_stepper.steppers[0].get_mcu_position()
        travel = ( mcu_position - init_mcu_pos ) * selector_steps
        delta = abs( target_move - travel )
        if delta <= 2.0 :
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
            self._servo_down()
            self.gcode.run_script_from_command("ERCF_LOAD LENGTH=45")
            self.gcode.run_script_from_command("G4 P50")
            # Try to unload
            self.gcode.run_script_from_command("ERCF_UNLOAD LENGTH=68")
            self._servo_up()
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
                self.selector_stepper.do_set_position( init_position + travel )
                self._selector_stepper_move_wait(target)
                return
            else :
                # Selector path is still blocked
                self.gcode.respond_info(
                    "Selector recovery failed, please check the ERCF,"
                    " calling ERCF_PAUSE...")
                self._unselect_tool()
                self._pause()
        else :
            # Selector path is blocked
            self.gcode.respond_info(
                "Selector path is blocked, "
                " please check the ERCF, calling ERCF_PAUSE...")
            self._unselect_tool()
            self._pause()

    def _set_steps(self, ratio=1.):
        self._log_trace("Setting ERCF gear motor step ratio to %.1f" % ratio)
        new_step_dist = self.ref_step_dist / ratio
        stepper = self.gear_stepper.rail.steppers[0]
        if hasattr(stepper, "set_rotation_distance"):
            new_rotation_dist = new_step_dist * stepper.get_rotation_distance()[1]
            stepper.set_rotation_distance(new_rotation_dist)
        else:
            # backwards compatibility for old klipper versions
            stepper.set_step_dist(new_step_dist)

    def _unselect_tool(self):
        if self.is_paused:
            self._log_info("Could not unselect tool, ERCF is paused")
            return
        
        if not self.is_homed:
            self._log_info("Could not unselect tool, ERCF is not homed")
            return

        self._servo_up()
        self._set_steps(1.)

    def _select_tool(self, tool):
        if self.is_paused:
            self._log_info("Could not select tool, ERCF is paused")
            return

        if not self.is_homed:
            self._log_info("Could not select tool, ERCF is not homed")
            return

        self._log_info("Select Tool %d..." % tool)
        self._servo_up()
        if self.sensorless_selector == 1:
            self._do_move_selector_sensorless(self.selector_offsets[tool])
        else:
            self._selector_stepper_move_wait(self.selector_offsets[tool])
        self.tool_selected = tool
        self._log_info("Tool %d Enabled" % tool)

    def _do_home_selector(self, tool = 0):
        self._log_info("Homing selector")
        self._servo_up()
        num_channels = len(self.selector_offsets)
        selector_length = 20. + num_channels*21. + (num_channels/3)*5.
        self._log_debug("Moving up to %.1fmm to home a %d channel ERCF" % (selector_length, num_channels))

        self.gcode.run_script_from_command("QUERY_ENDSTOPS")

        if self.sensorless_selector == 1:
            self.selector_stepper.do_set_position(0.)
            self.selector_stepper.do_homing_move(-selector_length, 60, self.selector_stepper.accel, True, True)
            self.selector_stepper.do_set_position(0.)
        else:
            self.selector_stepper.do_set_position(0.)
            self.selector_stepper.do_homing_move(-selector_length, 100, self.selector_stepper.accel, True, True)
            self.selector_stepper.do_set_position(0.)
            self.selector_stepper.do_move(5., 100, 0)
            self.selector_stepper.do_homing_move(-10, 10, self.selector_stepper.accel, True, True)
            self.selector_stepper.do_set_position(0.)     

        self.gcode.run_script_from_command("QUERY_ENDSTOPS")
        self.toolhead.wait_moves()
        self.selector_stepper.do_move(self.selector_offsets[tool], 50, self.selector_stepper.accel)
        self.toolhead.wait_moves()        
        endstop_lookup = 'manual_stepper selector_stepper'
        if self.sensorless_selector:
            endstop_lookup = 'manual_stepper gear_stepper'
        selector_state = self.printer.lookup_object("query_endstops").get_status(0)['last_query'][endstop_lookup]
        if selector_state != 1:
            self._log_info("Homing failed - check what is blocking the selector")
            self._pause()

    def _do_home(self, tool = 0):
        if self._get_calibration_version() != 2:
            self._log_info("You are running an old calibration version.  It is strongly recommended that you rerun 'ERCF_CALIBRATE_SINGLE TOOL=0' to generate an updated calibration value")
        self._disable_encoder_sensor()
        self.is_homed = True
        if self.is_paused:
            self._unlock()
        self._log_info("Homing ERCF...")        
        self._do_unload(self._get_calibration_ref(), True)
        self._do_home_selector(tool)       
        self.tool_selected = -1
        self._log_info("Homing ERCF ended...")         

    cmd_ERCF_CHANGE_TOOL_SLICER_help = "Perform a tool swap during a print"
    def cmd_ERCF_CHANGE_TOOL_SLICER(self, gcmd):
        if self.is_paused:
            return

        tool = gcmd.get_int('TOOL')
        if tool == self.tool_selected:
            return

        self._disable_encoder_sensor()
        self._do_unload_tool()
        self._do_load_tool(tool)
        if self.enable_clog_detection:
            self._enable_encoder_sensor()

    cmd_ERCF_CHANGE_TOOL_STANDALONE_help = "Perform a tool swap out of a print"
    def cmd_ERCF_CHANGE_TOOL_STANDALONE(self, gcmd):
        if self.is_paused:
            return

        tool = gcmd.get_int('TOOL')
        if tool == self.tool_selected and self.loaded_status == self.LOADED_STATUS_FULL:
            self._log_info('Tool %d is already selected' % tool)
            return

        if not self.is_homed:
            self._log_info('ERCF not homed, homing it...')
            self._do_home(tool)

        self._disable_encoder_sensor()
        self._do_unload(self._get_calibration_ref(), True)
        self._set_above_min_temp()
        self._do_load_tool(tool)

    cmd_ERCF_CHANGE_TOOL_help = "Perform a tool swap"
    def cmd_ERCF_CHANGE_TOOL(self, gcmd):
        tool = gcmd.get_int('TOOL')
        initial_tool_string = 'unknown tool' if self.tool_selected else ("T%d" % self.tool_selected)
        self._log_info("Tool swap requested, from %s to T%d" % (initial_tool_string, tool))
        self.gcode.run_script_from_command("M117 %s -> T%d" % (initial_tool_string, tool))
        if self._is_in_print():
            self.cmd_ERCF_CHANGE_TOOL_SLICER(gcmd)
        else:
            self.cmd_ERCF_CHANGE_TOOL_STANDALONE(gcmd)            
        self._track_swap_completed()
        self._dump_statistics()
        self._counter.reset_counts()

    cmd_ERCF_HOME_help = "Home the ERCF"
    def cmd_ERCF_HOME(self, gcmd):
        tool = gcmd.get_int('TOOL', 0)

        self._do_home(tool)

    cmd_ERCF_SELECT_TOOL_help = "Select the specified tool"
    def cmd_ERCF_SELECT_TOOL(self, gcmd):
        tool = gcmd.get_int('TOOL', 0)

        self._select_tool(tool)
        
############################
# RUNOUT AND ENDLESS SPOOL #        
############################
    cmd_ERCF_ENCODER_RUNOUT_help = "Encoder runout handler"
    def cmd_ERCF_ENCODER_RUNOUT(self, gcmd):
        if self.tool_selected == -1:
            self._log_info("Issue on an unknown tool - skipping clog/runout detection")    
            return

        self._log_info("Issue on tool %d" % self.tool_selected)
        self._log_info("Checking if this is a clog or a runout...")

        self._counter.reset_counts()
        self._disable_encoder_sensor()
        self._servo_down()
        self._do_buzz_gear_motor()
        self._servo_up()
        moved = self._counter.get_distance()
        if moved > 0.:
            self._log_info("A clog has been detected and requires manual intervention")
        else:
            self._log_info("A runout has been detected")
            # no movement means we are have a runout
            if self.enable_endless_spool:
                initial_pa = self.printer.lookup_object("extruder").get_status(0)['pressure_advance']
                self._log_info("EndlessSpool mode is ON!")
                next_check = self.tool_selected + 1
                next_tool = -1
                while next_check != self.tool_selected:
                    if next_check > len(self.selector_offsets):
                        next_check = 0
                    self._log_trace("Checking tool %d to see if it matches the right group" % next_check)
                    if self.endless_spool_groups[next_check] == self.endless_spool_groups[self.tool_selected]:
                        self._log_info("Found next tool in group: %d" % next_check)
                        next_tool = next_check
                        break
                    next_check += 1
                if next_tool == -1:
                    self._log_info("No more spools found in group %d - manual intervention is required" % self.endless_spool_groups[self.tool_selected])
                    return
                self.gcode.run_script_from_command("SAVE_GCODE_STATE NAME=ERCF_Pre_Brush_init")
                self.gcode.run_script_from_command("_ERCF_ENDLESS_SPOOL_PRE_UNLOAD")

                self._log_info("Unloading filament...")
                self.gcode.run_script_from_command("G91")
                self.gcode.run_script_from_command("_ERCF_FORM_TIP_STANDALONE")
                self._do_unload(self._get_calibration_ref(), False)
                self._do_load_tool(next_tool)
                self.gcode.run_script_from_command("SET_PRESSURE_ADVANCE ADVANCE=%.10f" % initial_pa)

                if self.is_paused:
                    self._log_info("ERCF is paused, cannot resume print")
                    return

                self.gcode.run_script_from_command("_ERCF_ENDLESS_SPOOL_POST_LOAD")
                self.gcode.run_script_from_command("RESTORE_GCODE_STATE NAME=ERCF_Pre_Brush_init")
                self.gcode.run_script_from_command("RESUME")
                self._enable_encoder_sensor()
            else:
                self._log_info("EndlessSpool mode is off - manual intervention is required")

#####################
# LOGGING FUNCTIONS #
#####################
    cmd_ERCF_SET_LOG_LEVEL_help = "Set the log level for the ERCF"
    def cmd_ERCF_SET_LOG_LEVEL(self, gcmd):
        self.log_level = gcmd.get_int('LEVEL', 1)

    def _log_info(self, message):
        if self.log_level > 0:
            self.gcode.respond_info(message)        

    def _log_debug(self, message):
        if self.log_level > 1:
            self.gcode.respond_info("DEBUG: %s" % message)        

    def _log_trace(self, message):
        if self.log_level > 2:
            self.gcode.respond_info("TRACE: %s" % message)      

def load_config(config):
    return Ercf(config)
