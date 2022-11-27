# Enraged Rabbit Carrot Feeder
#
# Copyright (C) 2021  Ette
#
# Major rewrite and feature updates Nov 2022  moggieuk#6538 (discord)
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
import copy
import logging
import math
import time
from random import randint
from . import force_move, pulse_counter

class EncoderCounter:
    def __init__(self, printer, pin, sample_time, poll_time, encoder_steps):
        self._last_time = self._last_count = None
        self._counts = 0
        self._encoder_steps = encoder_steps
        self._counter = pulse_counter.MCU_counter(printer, pin, sample_time, poll_time)
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
        return (self._counts / 2.) * self._encoder_steps

    def set_distance(self, new_distance):
        self._counts = int((new_distance / self._encoder_steps) * 2.)

    def reset_counts(self):
        self._counts = 0.

class ErcfError(Exception):
    pass

class Ercf:
    LONG_MOVE_THRESHOLD = 70.   # This is also the initial move to load past encoder
    SERVO_DOWN_STATE = 1
    SERVO_UP_STATE = 0
    SERVO_UNKNOWN_STATE = -1

    TOOL_UNKNOWN = -1
    TOOL_BYPASS = -2

    GATE_UNKNOWN = -1
    GATE_AVAILABLE = 1
    GATE_EMPTY = 0

    LOADED_STATUS_UNKNOWN = -1
    LOADED_STATUS_UNLOADED = 0
    LOADED_STATUS_PARTIAL_BEFORE_ENCODER = 1
    LOADED_STATUS_PARTIAL_PAST_ENCODER = 2
    LOADED_STATUS_PARTIAL_IN_BOWDEN = 3
    LOADED_STATUS_PARTIAL_END_OF_BOWDEN = 4
    LOADED_STATUS_PARTIAL_HOMED_EXTRUDER = 5
    LOADED_STATUS_PARTIAL_HOMED_SENSOR = 6
    LOADED_STATUS_PARTIAL_IN_EXTRUDER = 7
    LOADED_STATUS_FULL = 8

    DIRECTION_LOAD = 1
    DIRECTION_UNLOAD = -1

    # Extruder homing sensing strategies
    EXTRUDER_COLLISION = 0
    EXTRUDER_STALLGUARD = 1

    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.printer.register_event_handler("klippy:connect", self.handle_connect)

        # Manual steppers
        self.selector_stepper = self.gear_stepper = None
        self.encoder_pin = config.get('encoder_pin')
        self.encoder_resolution = config.getfloat('encoder_resolution', 0.5, above=0.)
        self.encoder_sample_time = config.getfloat('encoder_sample_time', 0.1, above=0.)
        self.encoder_poll_time = config.getfloat('encoder_poll_time', 0.0001, above=0.)
        self._counter = EncoderCounter(self.printer, self.encoder_pin, 
                                            self.encoder_sample_time,
                                            self.encoder_poll_time, 
                                            self.encoder_resolution)
        
        # Specific build parameters / tuning
        self.long_moves_speed = config.getfloat('long_moves_speed', 100.)
        self.short_moves_speed = config.getfloat('short_moves_speed', 25.)
        self.gear_homing_accel = config.getfloat('gear_homing_accel', 1000)
        self.gear_sync_accel = config.getfloat('gear_sync_accel', 1000)
        self.gear_buzz_accel = config.getfloat('gear_buzz_accel', 2000)
        self.servo_down_angle = config.getfloat('servo_down_angle')
        self.servo_up_angle = config.getfloat('servo_up_angle')
        self.extra_servo_dwell_down = config.getint('extra_servo_dwell_down', 0)
        self.extra_servo_dwell_up = config.getint('extra_servo_dwell_up', 0)
        self.num_moves = config.getint('num_moves', 2, minval=1)
        self.apply_bowden_correction = config.getint('apply_bowden_correction', 1, minval=0, maxval=1)
        self.load_bowden_tolerance = config.getfloat('load_bowden_tolerance', 8., minval=1., maxval=50.)
        self.unload_bowden_tolerance = config.getfloat('unload_bowden_tolerance', self.load_bowden_tolerance, minval=1., maxval=50.)
        self.parking_distance = config.getfloat('parking_distance', 23., above=15., below=30.)
        self.encoder_move_step_size = config.getfloat('encoder_move_step_size', 15., above=5., below=25.)
        self.selector_offsets = config.getfloatlist('colorselector')
        self.gate_status = list(config.getintlist('gate_status', []))
        self.bypass_offset = config.getfloat('bypass_selector', 0)
        self.timeout_pause = config.getint('timeout_pause', 72000)
        self.disable_heater = config.getint('disable_heater', 600)
        self.min_temp_extruder = config.getfloat('min_temp_extruder', 180.)
        self.calibration_bowden_length = config.getfloat('calibration_bowden_length')
        self.unload_buffer = config.getfloat('unload_buffer', 30., above=15.)
        self.home_to_extruder = config.getint('home_to_extruder', 1, minval=0, maxval=1)
        self.homing_method = config.getint('homing_method', 0, minval=0, maxval=1) # EXPERIMENTAL, not exposed yet
        self.extruder_homing_max = config.getfloat('extruder_homing_max', 50., above=20.)
        self.extruder_homing_step = config.getfloat('extruder_homing_step', 2., above=0.5, maxval=5.)
        self.extruder_homing_current = config.getint('extruder_homing_current', 50, minval=0, maxval=100)
        if self.extruder_homing_current == 0: self.extruder_homing_current = 100
        self.toolhead_homing_max = config.getfloat('toolhead_homing_max', 20., minval=0.)
        self.toolhead_homing_step = config.getfloat('toolhead_homing_step', 1., above=0.5, maxval=5.)
        self.sync_load_length = config.getfloat('sync_load_length', 8., minval=0., maxval=50.)
        self.sync_unload_length = config.getfloat('sync_unload_length', 10., minval=0., maxval=100.)
        self.delay_servo_release =config.getfloat('delay_servo_release', 2., minval=0., maxval=5.)
        self.home_position_to_nozzle = config.getfloat('home_position_to_nozzle', above=20.)

        # Options
        self.sensorless_selector = config.getint('sensorless_selector', 0, minval=0, maxval=1)
        self.enable_clog_detection = config.getint('enable_clog_detection', 1, minval=0, maxval=1)
        self.enable_endless_spool = config.getint('enable_endless_spool', 0, minval=0, maxval=1)
        self.endless_spool_groups = list(config.getintlist('endless_spool_groups', []))

        self.log_level = config.getint('log_level', 1, minval=0, maxval=4)
        self.log_statistics = config.getint('log_statistics', 0, minval=0, maxval=1)
        self.log_visual = config.getint('log_visual', 1, minval=0, maxval=1)

        if len(self.endless_spool_groups) > 0:
            if self.enable_endless_spool == 1 and len(self.endless_spool_groups) != len(self.selector_offsets):
                raise config.error("EndlessSpool mode requires that the endless_spool_groups parameter is set with the same number of values as the number of selectors")
        else:
            for i in range(len(self.selector_offsets)):
                self.endless_spool_groups.append(i)

        if len(self.gate_status) > 0:
            if not len(self.gate_status) == len(self.selector_offsets):
                raise config.error("Gate status map has different number of values than the number of selectors")
        else:
            for i in range(len(self.selector_offsets)):
                self.gate_status.append(self.GATE_AVAILABLE)

        # Setup tool to gate map primariliy for endless spool use
        self.tool_to_gate_map = []
        for i in range(len(self.selector_offsets)):
            self.tool_to_gate_map.append(i)


        # State variables
        self.is_paused = False
        self.is_homed = False
        self.paused_extruder_temp = 0.
        self.tool_selected = self.TOOL_UNKNOWN
        self.gate_selected = self.GATE_UNKNOWN  # We keep record of gate selected incase user messes with mapping in print
        self.servo_state = self.SERVO_UNKNOWN_STATE
        self.loaded_status = self.LOADED_STATUS_UNKNOWN
        self.filament_direction = self.DIRECTION_LOAD
        self.calibrating = False

        # Statistics
        self.total_swaps = 0
        self.time_spent_loading = 0
        self.time_spent_unloading = 0
        self.time_spent_paused = 0
        self.total_pauses = 0

        # Register GCODE commands
        self.gcode = self.printer.lookup_object('gcode')

        # Logging and Stats
        self.gcode.register_command('ERCF_RESET_STATS',
                    self.cmd_ERCF_RESET_STATS,
                    desc = self.cmd_ERCF_RESET_STATS_help)
        self.gcode.register_command('ERCF_DUMP_STATS',
                    self.cmd_ERCF_DUMP_STATS,
                    desc = self.cmd_ERCF_DUMP_STATS_help)
        self.gcode.register_command('ERCF_SET_LOG_LEVEL',
                    self.cmd_ERCF_SET_LOG_LEVEL,
                    desc = self.cmd_ERCF_SET_LOG_LEVEL_help)
        self.gcode.register_command('ERCF_DISPLAY_ENCODER_POS', 
                    self.cmd_ERCF_DISPLAY_ENCODER_POS,
                    desc = self.cmd_ERCF_DISPLAY_ENCODER_POS_help)                    
        self.gcode.register_command('ERCF_STATUS', 
                    self.cmd_ERCF_STATUS,
                    desc = self.cmd_ERCF_STATUS_help)                    

	# Calibration
        self.gcode.register_command('ERCF_CALIBRATE',
                    self.cmd_ERCF_CALIBRATE,
                    desc = self.cmd_ERCF_CALIBRATE_help)
        self.gcode.register_command('ERCF_CALIBRATE_SINGLE',
                    self.cmd_ERCF_CALIBRATE_SINGLE,
                    desc = self.cmd_ERCF_CALIBRATE_SINGLE_help)
        self.gcode.register_command('ERCF_CALIB_SELECTOR',
                    self.cmd_ERCF_CALIB_SELECTOR,
                    desc = self.cmd_ERCF_CALIB_SELECTOR_help)     
        self.gcode.register_command('ERCF_CALIBRATE_ENCODER',
                    self.cmd_ERCF_CALIBRATE_ENCODER,
                    desc=self.cmd_ERCF_CALIBRATE_ENCODER_help)

        # Servo and motor control
        self.gcode.register_command('ERCF_SERVO_DOWN',
                    self.cmd_ERCF_SERVO_DOWN,
                    desc = self.cmd_ERCF_SERVO_DOWN_help)                       
        self.gcode.register_command('ERCF_SERVO_UP',
                    self.cmd_ERCF_SERVO_UP,
                    desc = self.cmd_ERCF_SERVO_UP_help)
        self.gcode.register_command('ERCF_MOTORS_OFF',
                    self.cmd_ERCF_MOTORS_OFF,
                    desc = self.cmd_ERCF_MOTORS_OFF_help)
        self.gcode.register_command('ERCF_BUZZ_GEAR_MOTOR',
                    self.cmd_ERCF_BUZZ_GEAR_MOTOR,
                    desc=self.cmd_ERCF_BUZZ_GEAR_MOTOR_help)

	# Core ERCF functionality
        self.gcode.register_command('ERCF_HOME',
                    self.cmd_ERCF_HOME,
                    desc = self.cmd_ERCF_HOME_help)
        self.gcode.register_command('ERCF_SELECT_TOOL',
                    self.cmd_ERCF_SELECT_TOOL,
                    desc = self.cmd_ERCF_SELECT_TOOL_help)
        self.gcode.register_command('ERCF_PRELOAD',
                    self.cmd_ERCF_PRELOAD,
                    desc = self.cmd_ERCF_PRELOAD_help)
        self.gcode.register_command('ERCF_SELECT_BYPASS',
                    self.cmd_ERCF_SELECT_BYPASS,
                    desc = self.cmd_ERCF_SELECT_BYPASS_help)
        self.gcode.register_command('ERCF_LOAD_BYPASS',
                    self.cmd_ERCF_LOAD_BYPASS,
                    desc=self.cmd_ERCF_LOAD_BYPASS_help)
        self.gcode.register_command('ERCF_CHANGE_TOOL',
                    self.cmd_ERCF_CHANGE_TOOL,
                    desc = self.cmd_ERCF_CHANGE_TOOL_help)
        self.gcode.register_command('ERCF_EJECT',
                    self.cmd_ERCF_EJECT,
                    desc = self.cmd_ERCF_EJECT_help)
        self.gcode.register_command('ERCF_UNLOCK',
                    self.cmd_ERCF_UNLOCK,
                    desc = self.cmd_ERCF_UNLOCK_help)
        self.gcode.register_command('ERCF_PAUSE',
                    self.cmd_ERCF_PAUSE,
                    desc = self.cmd_ERCF_PAUSE_help)
        self.gcode.register_command('ERCF_RECOVER',
                    self.cmd_ERCF_RECOVER,
                    desc = self.cmd_ERCF_RECOVER_help)

	# User Testing
        self.gcode.register_command('ERCF_TEST_GRIP', 
                    self.cmd_ERCF_TEST_GRIP,
                    desc = self.cmd_ERCF_TEST_GRIP_help)
        self.gcode.register_command('ERCF_TEST_SERVO',
                    self.cmd_ERCF_TEST_SERVO,
                    desc = self.cmd_ERCF_TEST_SERVO_help)                          
        self.gcode.register_command('ERCF_TEST_MOVE_GEAR',
                    self.cmd_ERCF_TEST_MOVE_GEAR,
                    desc = self.cmd_ERCF_TEST_MOVE_GEAR_help)
        self.gcode.register_command('ERCF_TEST_LOAD_SEQUENCE',
                    self.cmd_ERCF_TEST_LOAD_SEQUENCE,
                    desc = self.cmd_ERCF_TEST_LOAD_SEQUENCE_help)
        self.gcode.register_command('ERCF_TEST_LOAD',
                    self.cmd_ERCF_TEST_LOAD,
                    desc=self.cmd_ERCF_TEST_LOAD_help)
        self.gcode.register_command('ERCF_LOAD',
                    self.cmd_ERCF_TEST_LOAD,
                    desc=self.cmd_ERCF_TEST_LOAD_help) # For backwards compatability because it's mentioned in manual, but prefer to remove
        self.gcode.register_command('ERCF_TEST_TRACKING',
                    self.cmd_ERCF_TEST_TRACKING,
                    desc=self.cmd_ERCF_TEST_TRACKING_help)
        self.gcode.register_command('ERCF_TEST_UNLOAD',
                    self.cmd_ERCF_TEST_UNLOAD,
                    desc=self.cmd_ERCF_TEST_UNLOAD_help)
        self.gcode.register_command('ERCF_TEST_HOME_TO_EXTRUDER',
                    self.cmd_ERCF_TEST_HOME_TO_EXTRUDER,
                    desc = self.cmd_ERCF_TEST_HOME_TO_EXTRUDER_help)    
        self.gcode.register_command('ERCF_TEST_CONFIG',
                    self.cmd_ERCF_TEST_CONFIG,
                    desc = self.cmd_ERCF_TEST_CONFIG_help)                    

        # Runout and Endless spool
        self.gcode.register_command('ERCF_ENCODER_RUNOUT', 
                    self.cmd_ERCF_ENCODER_RUNOUT,
                    desc = self.cmd_ERCF_ENCODER_RUNOUT_help)
        self.gcode.register_command('ERCF_DISPLAY_TTG_MAP',
                    self.cmd_ERCF_DISPLAY_TTG_MAP,
                    desc = self.cmd_ERCF_DISPLAY_TTG_MAP_help)
        self.gcode.register_command('ERCF_REMAP_TTG',
                    self.cmd_ERCF_REMAP_TTG,
                    desc = self.cmd_ERCF_REMAP_TTG_help)
        self.gcode.register_command('ERCF_RESET_TTG_MAP',
                    self.cmd_ERCF_RESET_TTG_MAP,
                    desc = self.cmd_ERCF_RESET_TTG_MAP_help)
        self.gcode.register_command('ERCF_CHECK_GATES',
                    self.cmd_ERCF_CHECK_GATES,
                    desc = self.cmd_ERCF_CHECK_GATES_help)


    def handle_connect(self):
        self.toolhead = self.printer.lookup_object('toolhead')
        for manual_stepper in self.printer.lookup_objects('manual_stepper'):
            stepper_name = manual_stepper[1].get_steppers()[0].get_name()
            if stepper_name == 'manual_stepper selector_stepper':
                self.selector_stepper = manual_stepper[1]
            if stepper_name == 'manual_stepper gear_stepper':
                self.gear_stepper = manual_stepper[1]
        if self.selector_stepper is None:
            raise config.error("Manual_stepper selector_stepper must be specified")
        if self.gear_stepper is None:
            raise config.error("Manual_stepper gear_stepper must be specified")

        # Get sensors
        self.encoder_sensor = self.printer.lookup_object("filament_motion_sensor encoder_sensor")
        try:
            self.toolhead_sensor = self.printer.lookup_object("filament_switch_sensor toolhead_sensor")
        except:
            self.toolhead_sensor = None
            if not self.home_to_extruder:
                self.home_to_extruder = 1
                self._log_debug("No toolhead sensor detected, forcing home_to_extruder")

        # Get endstops
        self.query_endstops = self.printer.lookup_object('query_endstops')
        self.selector_endstop = self.gear_endstop = None
        for endstop, name in self.query_endstops.endstops:
            if name == 'manual_stepper selector_stepper':
                self.selector_endstop = endstop
            if name == 'manual_stepper gear_stepper':
                self.gear_endstop = endstop
        if self.selector_endstop == None:
            raise self.config.error("Selector endstop must be specified")
        if self.sensorless_selector and self.gear_endstop == None:
            raise self.config.error("Gear stepper endstop must be configured for sensorless selector operation")

        # See if we have a TMC controller capable of current control for filament collision method (just 2209 for now)
        self.tmc = None
        try:
            self.tmc = self.printer.lookup_object('tmc2209 manual_stepper gear_stepper')
        except:
            self._log_debug("TMC driver not found, cannot use current reduction for collision detection")

        self.ref_step_dist=self.gear_stepper.steppers[0].get_step_dist()
        self.variables = self.printer.lookup_object('save_variables').allVariables
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        self._reset_statistics()

        # Override motion sensor runout detection_length based on calibration
        self.encoder_sensor.detection_length = self._get_calibration_clog_length()

    def handle_ready(self):
        self._setup_heater_off_reactor()
        self._log_always('(\_/)\n( *,*)\n(")_(") ERCF Ready\n')


####################################
# LOGGING AND STATISTICS FUNCTIONS #
####################################

    def get_status(self, eventtime):
        encoder_pos = float(self._counter.get_distance())
        return {'encoder_pos': encoder_pos, 'is_paused': self.is_paused, 'tool': self.tool_selected, 'gate': self.gate_selected, 'clog_detection': self.enable_clog_detection}

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

    def _statistics_to_human_string(self):
        msg = "ERCF Statistics:"
        msg += "\n%d Swaps Completed" % self.total_swaps
        msg += "\n%s spent loading" % self._seconds_to_human_string(self.time_spent_loading)
        msg += "\n%s spent unloading" % self._seconds_to_human_string(self.time_spent_unloading)
        msg += "\n%s spent paused (%d pauses total)" % (self._seconds_to_human_string(self.time_spent_paused), self.total_pauses)
        return msg

    def _dump_statistics(self, report=False):
        if self.log_statistics or report:
            self._log_info(self._statistics_to_human_string())

    def _log_always(self, message):
        self.gcode.respond_info(message)

    def _log_info(self, message):
        if self.log_level > 0:
            self.gcode.respond_info(message)

    def _log_debug(self, message):
        if self.log_level > 1:
            self.gcode.respond_info("- DEBUG: %s" % message)

    def _log_trace(self, message):
        if self.log_level > 2:
            self.gcode.respond_info("- - TRACE: %s" % message)

    def _log_stepper(self, message):
        if self.log_level > 3:
            self.gcode.respond_info("- - - STEPPER: %s" % message)

    # Fun visual display of ERCF state
    def _display_visual_state(self, direction=None):
        if not direction == None:
            self.filament_direction = direction
        if self.log_visual and not self.calibrating:
            self._log_always(self._state_to_human_string())

    def _state_to_human_string(self, direction=None):
        tool_str = str(self.tool_selected) if self.tool_selected >=0 else "?"
        sensor_str = " [sensor] " if self.toolhead_sensor != None else ""
        counter_str = " (@%.1f mm)" % self._counter.get_distance()
        visual = ""
        if self.tool_selected == self.TOOL_BYPASS:
            visual = "ERCF BYPASS -------- [encoder] -------------->>"
        elif self.loaded_status == self.LOADED_STATUS_UNKNOWN:
            visual = "ERCF [T%s] ..... [encoder] .............. [extruder] .....%s.... [nozzle] UNKNOWN" % (tool_str, sensor_str)
        elif self.loaded_status == self.LOADED_STATUS_UNLOADED:
            visual = "ERCF [T%s] >.... [encoder] .............. [extruder] .....%s.... [nozzle] UNLOADED" % (tool_str, sensor_str)
            visual += counter_str
        elif self.loaded_status == self.LOADED_STATUS_PARTIAL_BEFORE_ENCODER:
            visual = "ERCF [T%s] >>>.. [encoder] .............. [extruder] .....%s.... [nozzle]" % (tool_str, sensor_str)
            visual += counter_str
        elif self.loaded_status == self.LOADED_STATUS_PARTIAL_PAST_ENCODER:
            visual = "ERCF [T%s] >>>>> [encoder] >>>........... [extruder] .....%s.... [nozzle]" % (tool_str, sensor_str)
            visual += counter_str
        elif self.loaded_status == self.LOADED_STATUS_PARTIAL_IN_BOWDEN:
            visual = "ERCF [T%s] >>>>> [encoder] >>>>>>>>...... [extruder] .....%s.... [nozzle]" % (tool_str, sensor_str)
            visual += counter_str
        elif self.loaded_status == self.LOADED_STATUS_PARTIAL_END_OF_BOWDEN:
            visual = "ERCF [T%s] >>>>> [encoder] >>>>>>>>>>>>>> [extruder] .....%s.... [nozzle]" % (tool_str, sensor_str)
            visual += counter_str
        elif self.loaded_status == self.LOADED_STATUS_PARTIAL_HOMED_EXTRUDER:
            visual = "ERCF [T%s] >>>>> [encoder] >>>>>>>>>>>>>| [extruder] .....%s.... [nozzle]" % (tool_str, sensor_str)
            visual += counter_str
        elif self.loaded_status == self.LOADED_STATUS_PARTIAL_HOMED_SENSOR:
            visual = "ERCF [T%s] >>>>> [encoder] >>>>>>>>>>>>>> [extruder] >>>>|%s.... [nozzle]" % (tool_str, sensor_str)
            visual += counter_str
        elif self.loaded_status == self.LOADED_STATUS_PARTIAL_IN_EXTRUDER:
            visual = "ERCF [T%s] >>>>> [encoder] >>>>>>>>>>>>>> [extruder] >>>>.%s.... [nozzle]" % (tool_str, sensor_str)
            visual += counter_str
        elif self.loaded_status == self.LOADED_STATUS_FULL:
            visual = "ERCF [T%s] >>>>> [encoder] >>>>>>>>>>>>>> [extruder] >>>>>%s>>>> [nozzle] LOADED" % (tool_str, sensor_str)
            visual += counter_str
        if self.filament_direction == self.DIRECTION_UNLOAD:
            visual = visual.replace(">", "<")
        return visual

### LOGGING AND STATISTICS FUNCTIONS GCODE FUNCTIONS

    cmd_ERCF_RESET_STATS_help = "Reset the ERCF statistics"
    def cmd_ERCF_RESET_STATS(self, gcmd):
        self._reset_statistics()

    cmd_ERCF_DUMP_STATS_help = "Dump the ERCF statistics"
    def cmd_ERCF_DUMP_STATS(self, gcmd):
        self._dump_statistics(True)

    cmd_ERCF_SET_LOG_LEVEL_help = "Set the log level for the ERCF"
    def cmd_ERCF_SET_LOG_LEVEL(self, gcmd):
        self.log_level = gcmd.get_int('LEVEL', 1, minval=0, maxval=4)
        self.log_visual = gcmd.get_int('VISUAL', 1, minval=0, maxval=1)

    cmd_ERCF_DISPLAY_ENCODER_POS_help = "Display current value of the ERCF encoder"
    def cmd_ERCF_DISPLAY_ENCODER_POS(self, gcmd):
        self._log_info("Encoder value is %.2f" % self._counter.get_distance())

    cmd_ERCF_STATUS_help = "Complete dump of current ERCF state and important configuration"
    def cmd_ERCF_STATUS(self, gcmd):
        config = gcmd.get_int('SHOWCONFIG', 1, minval=0, maxval=1)
        msg = "ERCF with %d gates" % (len(self.selector_offsets))
        msg += " is %s" % ("PAUSED/LOCKED" if self.is_paused else "OPERATIONAL")
        msg += " with the servo in a %s position" % ("UP" if self.servo_state == self.SERVO_UP_STATE else "DOWN" if self.servo_state == self.SERVO_DOWN_STATE else "unknown")
        msg += ", Encoder reads %.2fmm" % self._counter.get_distance()
        msg += "\nTool %s is selected " % self._selected_tool_string()
        msg += " on gate %s" % self._selected_gate_string()
        msg += "\nFilament position: %s" % self._state_to_human_string()
        
        if config:
            msg += "\n\nConfiguration:\nFilament homes "
            if self.home_to_extruder:
                if self.homing_method == self.EXTRUDER_COLLISION:
                    msg += "to EXTRUDER using COLLISION DETECTION (current %d%%)" % self.extruder_homing_current
                else:
                    msg += "to EXTRUDER using STALLGUARD"
                if self.toolhead_sensor != None:
                    msg += " and then"
            msg += " to TOOLHEAD SENSOR" if self.toolhead_sensor != None else ""
            msg += " after a %.1fmm calibration reference length" % self._get_calibration_ref()
            msg += "\nGear and Extruder steppers are synchronized during "
            load = False
            if self.toolhead_sensor != None and self.sync_load_length > 0:
                msg += "load (up to %.1fmm)" % (self.toolhead_homing_max)
                load = True
            elif self.sync_load_length > 0:
                msg += "load (%.1fmm)" % (self.sync_load_length)
                load = True
            if self.sync_unload_length > 0:
                msg += " and " if load else ""
                msg += "unload (%.1fmm)" % (self.sync_unload_length)
            msg += "\nSelector homing is %s - blocked gate detection and recovery %s possible" % (("sensorless", "may be") if self.sensorless_selector else ("microswitch", "is not"))
            msg += "\nClog detection is %s" % ("ENABLED" if self.enable_clog_detection else "DISABLED")
            msg += " and EndlessSpool is %s" % ("ENABLED" if self.enable_endless_spool else "DISABLED")
            log = "ESSENTIAL MESSAGES"
            if self.log_level > 3:
                log = "STEPPER"
            elif self.log_level > 2:
                log = "TRACE"
            elif self.log_level > 1:
                log = "DEBUG"
            elif self.log_level > 0:
                log = "INFO"
            msg += "\nLogging level is %d (%s)" % (self.log_level, log)
            msg += "%s" % " and statistics are being logged" if self.log_statistics else ""
        msg += "\n\nTool/gate mapping%s" % (" and EndlessSpool groups:" if self.enable_endless_spool else ":")
        msg += "\n%s" % self._tool_to_gate_map_to_human_string()
        msg += "\n\n%s" % self._statistics_to_human_string()
        self._log_always(msg)


#############################
# SERVO AND MOTOR FUNCTIONS #
#############################

    def _servo_set_angle(self, angle):
        self.servo_state = self.SERVO_UNKNOWN_STATE 
        self.gcode.run_script_from_command("SET_SERVO SERVO=ercf_servo ANGLE=%1.f" % angle)

    def _servo_off(self):
        self.gcode.run_script_from_command("SET_SERVO SERVO=ercf_servo WIDTH=0.0")

    def _servo_down(self):
        if self.servo_state == self.SERVO_DOWN_STATE: return
        if self.tool_selected == self.TOOL_BYPASS: return
        self._log_debug("Setting servo to down angle: %d" % (self.servo_down_angle))
        self.toolhead.wait_moves()
        self._gear_stepper_move_wait(0.5, speed=25, accel=self.gear_buzz_accel, wait=False, sync=False)
        self._servo_set_angle(self.servo_down_angle)
        self.toolhead.dwell(0.2)
        self._gear_stepper_move_wait(-0.5, speed=25, accel=self.gear_buzz_accel, wait=False, sync=False)
        self.toolhead.dwell(0.1)
        self._gear_stepper_move_wait(0.5, speed=25, accel=self.gear_buzz_accel, wait=False, sync=False)
        self.toolhead.dwell(0.1 + self.extra_servo_dwell_down / 1000.)
        self._gear_stepper_move_wait(-0.5, speed=25, accel=self.gear_buzz_accel, wait=True, sync=True)
        self._servo_off()
        self.servo_state = self.SERVO_DOWN_STATE

    def _servo_up(self):
        if self.servo_state == self.SERVO_UP_STATE: return 0.
        initial_encoder_position = self._counter.get_distance()
        self._log_debug("Setting servo to up angle: %d" % (self.servo_up_angle))
        self.toolhead.wait_moves()
        self._servo_set_angle(self.servo_up_angle)
        self.toolhead.dwell(0.25 + self.extra_servo_dwell_up / 1000.)
        self._servo_off()
        self.servo_state = self.SERVO_UP_STATE

        # Report on spring back in filament then reset counter
        self.toolhead.dwell(0.3)
        self.toolhead.wait_moves()
        delta = self._counter.get_distance() - initial_encoder_position
        if delta > 0.:
            self._log_debug("Spring in filament measured  %.1fmm - adjusting encoder" % delta)
            self._counter.set_distance(initial_encoder_position)
        return delta

### SERVO AND MOTOR GCODE FUNCTIONS

    cmd_ERCF_SERVO_UP_help = "Disengage the ERCF gear"
    def cmd_ERCF_SERVO_UP(self, gcmd):
        if self._check_is_paused(): return
        self._servo_up()

    cmd_ERCF_SERVO_DOWN_help = "Engage the ERCF gear"
    def cmd_ERCF_SERVO_DOWN(self, gcmd):
        if self._check_is_paused(): return
        self._servo_down()

    cmd_ERCF_MOTORS_OFF_help = "Turn off both ERCF motors"
    def cmd_ERCF_MOTORS_OFF(self, gcmd):
        self.gear_stepper.do_enable(False)
        self.selector_stepper.do_enable(False)
        self.is_homed = False
        self._set_tool_selected(self.TOOL_UNKNOWN, True)

    cmd_ERCF_BUZZ_GEAR_MOTOR_help = "Buzz the ERCF gear motor"
    def cmd_ERCF_BUZZ_GEAR_MOTOR(self, gcmd):
        found = self._buzz_gear_motor()
        self._log_info("Filament %s by gear motor buzz" % ("detected" if found else "not detected"))


#########################
# CALIBRATION FUNCTIONS #
#########################

    def _get_calibration_version(self):
        return self.variables.get('ercf_calib_version', 1)

    def _get_calibration_ref(self):
        return self.variables.get('ercf_calib_ref', 500.)

    def _get_gate_ratio(self, gate):
        if gate < 0: return 1.
        return self.variables.get('ercf_calib_%d' % gate, 1.)

    def _get_calibration_clog_length(self):
        return max(self.variables.get('ercf_calib_clog_length', 7.), 5.)

    def _calculate_calibration_ref(self, extruder_homing_length=400, repeats=3):
        self._log_always("Calibrating reference tool T0")
        self._select_tool(0)
        self._set_steps(1.)
        reference_sum = spring_sum = 0.
        successes = 0
        try:
            for i in range(repeats):
                self._servo_down()
                self._counter.reset_counts()    # Encoder 0000
                encoder_moved = self._load_encoder()
                self._load_bowden(self.calibration_bowden_length - encoder_moved)     
                self._log_info("Finding extruder gear position (try #%d of %d)..." % (i+1, repeats))
                self._home_to_extruder(extruder_homing_length)
                measured_movement = self._counter.get_distance()
                spring = self._servo_up()
                reference = measured_movement - (spring * 0.1)
                if spring > 0:
                    if self.home_to_extruder:
                        # Home to extruder step is enabled so we don't need any spring
                        # in filament since we will do it again on every load
                        reference = measured_movement - (spring * 1.0)
                    elif self.sync_load_length > 0:
                        # Synchronized load makes the transition from gear stepper to extruder stepper
                        # work reliably so we don't need spring tension in the bowden
                        if self.toolhead_sensor != None:
                            # We have a toolhead sensor so the extruder entrance isn't the reference
                            # homing point and therefore not critical to press against it. Relax tension
                            reference = measured_movement - (spring * 1.1) 
                        else:
                            # We need a little bit of tension because sync load is more reliable in
                            # picking up filament but we still rely on the extruder as home point
                            reference = measured_movement - (spring * 0.5)
        
                    msg = "Pass #%d: Filament homed to extruder, encoder measured %.1fmm" % (i+1, measured_movement)
                    msg += "\nFilament sprung back %.1fmm when servo released" % spring
                    msg += "\nCalibration reference based on this pass is %.1f" % reference
                    self._log_always(msg)
                    reference_sum += reference
                    spring_sum += spring
                    successes += 1
                else:
                    # No spring means we haven't reliably homed
                    self._log_always("Failed to detect a reliable home position on this attempt")

                self._counter.reset_counts()    # Encoder 0000
                self._unload_bowden(reference - self.unload_buffer)
                self._unload_encoder(self.unload_buffer)
                self._set_loaded_status(self.LOADED_STATUS_UNLOADED)
    
            if successes > 0:
                average_reference = reference_sum / successes
                average_spring_detection_length = (spring_sum / successes) * 2.0
                self._log_always("Recommended calibration reference based on current configuration options is %.1f" % average_reference)
                self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=ercf_calib_ref VALUE=%.1f" % average_reference)
                self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=ercf_calib_clog_length VALUE=%.1f" % average_spring_detection_length)
                self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=ercf_calib_0 VALUE=1.0")  
                self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=ercf_calib_version VALUE=3")
                if self.enable_clog_detection:
                    self._log_always("Recommended setting for 'detection_length' in the encoder_sensor config is: %.1f" % average_spring_detection_length)
                else:
                    self._log_always("If you choose to enable the clog detection option the recommended setting for 'detection_length' is: %.1f" % average_spring_detection_length)
            else:
                self._log_always("All %d attempts at homing failed. ERCF needs some adjustments!" % repeats)
        except ErcfError as ee:
            # Add some more context to the error and re-raise
            raise ErcfError("Calibration of reference tool T0 failed. Aborting, because:\n%s" % ee.message)
        finally:
            self._servo_up()

    def _calculate_calibration_ratio(self, tool):
        load_length = self.calibration_bowden_length - 100.
        self._select_tool(tool)
        self._set_steps(1.)
        try:
            self._servo_down()
            self._counter.reset_counts()    # Encoder 0000
            encoder_moved = self._load_encoder()
            test_length = load_length - encoder_moved
            delta = self._trace_filament_move("Calibration load movement", test_length, speed=self.long_moves_speed)
            delta = self._trace_filament_move("Calibration unload movement", -test_length, speed=self.long_moves_speed)
            measurement = self._counter.get_distance()
            ratio = (test_length * 2) / (measurement - encoder_moved)
            self._log_always("Calibration move of %.1fmm, average encoder measurement %.1fmm - Ratio is %.6f" % (test_length * 2, measurement - encoder_moved, ratio))
            if not tool == 0:
                self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=ercf_calib_%d VALUE=%.6f" % (tool, ratio))  
            self._unload_encoder(self.unload_buffer)
            self._servo_up()
            self._set_loaded_status(self.LOADED_STATUS_UNLOADED)
        except ErcfError as ee:
            # Add some more context to the error and re-raise
            raise ErcfError("Calibration for tool T%d failed. Aborting, because: %s" % (tool, ee.message))
        finally:
            self._servo_up()

    def _sample_stats(self, values):
        mean = stdev = vmin = vmax = 0.
        if values:
            mean = sum(values) / len(values)
            diff2 = [( v - mean )**2 for v in values]
            stdev = math.sqrt( sum(diff2) / max((len(values) - 1), 1))
            vmin = min(values)
            vmax = max(values)
        return {'mean': mean, 'stdev': stdev, 'min': vmin, 'max': vmax, 'range': vmax - vmin}        

### CALIBRATION GCODE COMMANDS

    cmd_ERCF_CALIBRATE_help = "Complete calibration of all ERCF Tools"
    def cmd_ERCF_CALIBRATE(self, gcmd):
        if self._check_is_paused(): return
        try:
            self.calibrating = True
            self._disable_encoder_sensor()
            self._log_always("Start the complete auto calibration...")
            self._home(0)
            for i in range(len(self.selector_offsets)):
                if i == 0:
                    self._calculate_calibration_ref()
                else:
                    self._calculate_calibration_ratio(i)
            self._log_always("End of the complete auto calibration!")
            self._log_always("Please reload the firmware for the calibration to be active!")
        except ErcfError as ee:
            self._pause(ee.message)
        finally:
            self.calibrating = False

    cmd_ERCF_CALIBRATE_SINGLE_help = "Calibration of a single ERCF Tool"
    def cmd_ERCF_CALIBRATE_SINGLE(self, gcmd):
        if self._check_is_paused(): return
        tool = gcmd.get_int('TOOL', 0, minval=0, maxval=len(self.selector_offsets)-1)
        repeats = gcmd.get_int('REPEATS', 3, minval=1, maxval=10)
        validate = gcmd.get_int('VALIDATE', 0, minval=0, maxval=1)
        try:
            self.calibrating = True
            self._home(tool)
            if tool == 0 and not validate:
                self._calculate_calibration_ref(repeats=repeats)
            else:
                self._calculate_calibration_ratio(tool)
        except ErcfError as ee:
            self._pause(ee.message)
        finally:
            self.calibrating = False

    cmd_ERCF_CALIBRATE_ENCODER_help = "Calibration routine for the ERCF encoder"
    def cmd_ERCF_CALIBRATE_ENCODER(self, gcmd):
        if self._check_is_paused(): return
        dist = gcmd.get_float('DIST', 500., above=0.)
        repeats = gcmd.get_int('RANGE', 5, minval=1)
        speed = gcmd.get_float('SPEED', self.long_moves_speed, above=0.)
        accel = gcmd.get_float('ACCEL', self.gear_stepper.accel, above=0.)
        try:
            self.calibrating = True
            plus_values, min_values = [], []
            for x in range(repeats):
                # Move forward
                self._counter.reset_counts()    # Encoder 0000
                self._gear_stepper_move_wait(dist, True, speed, accel)
                plus_values.append(self._counter.get_counts())
                self._log_always("+ counts =  %.3f"
                            % (self._counter.get_counts()))
                # Move backward
                self._counter.reset_counts()    # Encoder 0000
                self._gear_stepper_move_wait(-dist, True, speed, accel)
                min_values.append(self._counter.get_counts())
                self._log_always("- counts =  %.3f"
                            % (self._counter.get_counts()))
                if self._counter.get_counts() == 0:
                    break
    
            self._log_always("Load direction: mean=%(mean).2f stdev=%(stdev).2f"
                              " min=%(min)d max=%(max)d range=%(range)d"
                              % self._sample_stats(plus_values))
            self._log_always("Unload direction: mean=%(mean).2f stdev=%(stdev).2f"
                              " min=%(min)d max=%(max)d range=%(range)d"
                              % self._sample_stats(min_values))
    
            mean_plus = self._sample_stats(plus_values)['mean']
            mean_minus = self._sample_stats(min_values)['mean']
            half_mean = (float(mean_plus) + float(mean_minus)) / 4
    
            if half_mean == 0:
                self._log_always("No counts measured. Ensure a tool was selected with servo down " +
                                  "before running calibration and that your encoder " +
                                  "is working properly")
                return
            resolution = dist / half_mean
            old_result = half_mean * self.encoder_resolution
            new_result = half_mean * resolution
    
            self._log_always("Before calibration measured length = %.6f" % old_result)
            self._log_always("Resulting resolution for the encoder = %.6f" % resolution)
            self._log_always("After calibration measured length = %.6f" % new_result)
            self._log_always("IMPORTANT: Don't forget to update 'encoder_resolution: %.6f' in your ercf_parameters.cfg file and restart Klipper" % resolution)
        except ErcfError as ee:
            self._pause(ee.message)
        finally:
            self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_BOWDEN)
            self.calibrating = False

    cmd_ERCF_CALIB_SELECTOR_help = "Calibration of the selector position for a defined Tool"
    def cmd_ERCF_CALIB_SELECTOR(self, gcmd):
        if self._check_is_paused(): return
        tool = gcmd.get_int('TOOL', 0, minval=0, maxval=len(self.selector_offsets)-1)
        try:
            self.calibrating = True
            self._servo_up()
            move_length = 10. + tool*21 + (tool//3)*5 + (self.bypass_offset > 0)
            self._log_always("Measuring the selector position for tool %d" % tool)
            self.selector_stepper.do_set_position(0.)
            init_position = self.selector_stepper.steppers[0].get_mcu_position()
            self._selector_stepper_move_wait(-move_length, speed=60, homing_move=1)
            current_position = self.selector_stepper.steppers[0].get_mcu_position()
            traveled_position = abs(current_position - init_position) * self.selector_stepper.steppers[0].get_step_dist()

            # Test we actually homed, if not we didn't move far enough
            if self.sensorless_selector == 1:
                homed = self.gear_endstop.query_endstop(self.toolhead.get_last_move_time())
            else:
                homed = self.selector_endstop.query_endstop(self.toolhead.get_last_move_time())
            if not homed:
                self._log_always("Selector didn't find home postion. Are you sure you selected the correct tool?")
            else:
                self._log_always("Selector position = %.1fmm" % traveled_position)
        except ErcfError as ee:
            self._pause(ee.message)
        finally:
            self.calibrating = False


########################
# ERCF STATE FUNCTIONS #
########################

    def _setup_heater_off_reactor(self):
        self.reactor = self.printer.get_reactor()
        self.heater_off_handler = self.reactor.register_timer(self._handle_pause_timeout, self.reactor.NEVER)

    def _handle_pause_timeout(self, eventtime):
        self._log_info("Disable extruder heater")
        self.gcode.run_script_from_command("M104 S0")
        return self.reactor.NEVER

    def _pause(self, reason):
        if self.is_paused: return
        self.is_paused = True
        self._track_pause_start()
        self.paused_extruder_temp = self.printer.lookup_object("extruder").heater.target_temp
        self.gcode.run_script_from_command("SET_IDLE_TIMEOUT TIMEOUT=%d" % self.timeout_pause)
        self.reactor.update_timer(self.heater_off_handler, self.reactor.monotonic() + self.disable_heater)
        msg = "An issue with the ERCF has been detected and the ERCF has been PAUSED"
        msg += "\nReason: %s" % reason
        msg += "\nWhen you intervene to fix the issue, first call \"ERCF_UNLOCK\""
        msg += "\nRefer to the manual before resuming the print"
        self.gcode.respond_raw("!! %s" % msg)   # non highlighted alternative self._log_always(msg)
        self.gcode.run_script_from_command("SAVE_GCODE_STATE NAME=ERCF_state")
        self._disable_encoder_sensor()
        self.gcode.run_script_from_command("PAUSE")

    def _unlock(self):
        if not self.is_paused: return
        self._unselect_tool()
        self.loaded_status = self.LOADED_STATUS_UNKNOWN
        self.reactor.update_timer(self.heater_off_handler, self.reactor.NEVER)
        self.gcode.run_script_from_command("M104 S%.1f" % self.paused_extruder_temp)
        self.gcode.run_script_from_command("RESTORE_GCODE_STATE NAME=ERCF_state")
        self._counter.reset_counts()    # Encoder 0000
        self._track_pause_end()
        self.is_paused = False

    def _disable_encoder_sensor(self):
        self._log_trace("Disable encoder sensor")
        self.encoder_sensor.runout_helper.sensor_enabled = 0

    def _enable_encoder_sensor(self):
        self._log_trace("Enable encoder sensor")
        self.encoder_sensor.runout_helper.sensor_enabled = 1

    def _check_is_paused(self):
        if self.is_paused:
            self._log_always("ERCF is currently paused.  Please use ERCF_UNLOCK")
            return True
        return False

    def _check_in_bypass(self):
        if self.tool_selected == self.TOOL_BYPASS:
            self._log_always("Operation not possible. ERCF is currently using bypass")
            return True
        return False

    def _check_not_homed(self):
        if not self.is_homed:
            self._log_always("ERCF is not homed")
            return True
        return False

    def _check_is_loaded(self):
        if not (self.loaded_status == self.LOADED_STATUS_UNLOADED or self.loaded_status == self.LOADED_STATUS_UNKNOWN):
            self._log_always("ERCF already has filament loaded")
            return True
        return False

    def _is_in_print(self):
        status = self.printer.lookup_object("idle_timeout").get_status(self.printer.get_reactor().monotonic())
        if self.printer.lookup_object("pause_resume").is_paused:
            status["state"] = "Paused"
        return status["state"] == "Printing" and status["printing_time"] > 2.0

    def _set_above_min_temp(self):
        if not self.printer.lookup_object("extruder").heater.can_extrude :
            self._log_info("M118 Heating extruder above min extrusion temp (%.1f)" % self.min_temp_extruder)
            self.gcode.run_script_from_command("M109 S%.1f" % self.min_temp_extruder)

    def _set_loaded_status(self, state, silent=False):
            self.loaded_status = state
            if not silent:
                self._display_visual_state()

    def _selected_tool_string(self):
        if self.tool_selected == self.TOOL_BYPASS:
            return "bypass"
        elif self.tool_selected == self.TOOL_UNKNOWN:
            return "unknown"
        else:
            return "T%d" % self.tool_selected

    def _selected_gate_string(self):
        if self.tool_selected == self.TOOL_BYPASS:
            return "bypass"
        elif self.gate_selected == self.GATE_UNKNOWN:
            return "unknown"
        else:
            return "#%d" % self.gate_selected

    def _is_filament_in_bowden(self):
        if self.loaded_status == self.LOADED_STATUS_PARTIAL_PAST_ENCODER or self.loaded_status == self.LOADED_STATUS_PARTIAL_IN_BOWDEN:
            return True
        return False


####################################################################################
# GENERAL MOTOR HELPERS - All stepper movements should go through here for tracing #
####################################################################################

    def _gear_stepper_move_wait(self, dist, wait=True, speed=None, accel=None, sync=True):
        self.gear_stepper.do_set_position(0.)   # All gear moves are relative
        is_long_move = abs(dist) > self.LONG_MOVE_THRESHOLD
        if speed is None:
            speed = self.long_moves_speed if is_long_move else self.short_moves_speed
        if accel is None:
            accel = self.gear_stepper.accel
        self._log_stepper("GEAR: dist=%.1f, speed=%d, accel=%d" % (dist, speed, accel))
        self.gear_stepper.do_move(dist, speed, accel, sync)
        if wait:
            self.toolhead.wait_moves()

    # Convenience wrapper around a gear and extrduer motor move that tracks measured movement and create trace log entry
    def _trace_filament_move(self, trace_str, distance, speed=None, accel=None, motor="gear"):
        if speed == None:
            speed = self.gear_stepper.velocity
        start = self._counter.get_distance()
        trace_str += ". Stepper: '%s' moved %%.1fmm, encoder measured %%.1fmm (delta %%.1fmm)" % motor
        if motor == "both":
            self._log_stepper("BOTH: dist=%.1f, speed=%d, accel=%d" % (distance, speed, self.gear_sync_accel))
            self.gear_stepper.do_set_position(0.)                   # Make incremental move
            pos = self.toolhead.get_position()
            pos[3] += distance
            self.gear_stepper.do_move(distance, speed, self.gear_sync_accel, False)
            self.toolhead.manual_move(pos, speed)
            self.toolhead.dwell(0.05)                               # "MCU Timer too close" protection
            self.toolhead.wait_moves()
            self.toolhead.set_position(pos)                         # Force subsequent incremental move
        elif motor == "gear":
            self._gear_stepper_move_wait(distance, accel=accel)
        else:   # extruder only
            self._log_stepper("EXTRUDER: dist=%.1f, speed=%d" % (distance, speed))
            pos = self.toolhead.get_position()
            pos[3] += distance
            self.toolhead.manual_move(pos, speed)
            self.toolhead.wait_moves()
            self.toolhead.set_position(pos)                         # Force subsequent incremental move

        end = self._counter.get_distance()
        measured = end - start
        # delta: +ve means measured less than moved, -ve means measured more than moved
        delta = abs(distance) - measured
        trace_str += ". Counter: @%.1fmm" % end
        self._log_trace(trace_str % (distance, measured, delta))
        return delta

    def _selector_stepper_move_wait(self, dist, wait=True, speed=None, accel=None, homing_move=0):
        if speed == None:
            speed = self.selector_stepper.velocity
        if accel == None:
            accel = self.selector_stepper.accel
        if homing_move:
            self.toolhead.wait_moves() # Necessary before homing move
            self.selector_stepper.do_homing_move(dist, speed, accel, homing_move > 0, abs(homing_move) == 1)
        else:
            self.selector_stepper.do_move(dist, speed, accel)
        if wait:
            self.toolhead.wait_moves()

    def _buzz_gear_motor(self):
        initial_encoder_position = self._counter.get_distance()
        self._gear_stepper_move_wait(2.0, wait=False)
        self._gear_stepper_move_wait(-2.0)        
        delta = self._counter.get_distance() - initial_encoder_position
        self._log_trace("After buzzing gear motor, encoder moved %.2f" % delta)
        self._counter.set_distance(initial_encoder_position)
        return delta > 0.0

    # Check for filament in encoder by wiggling ERCF gear stepper and looking for movement on encoder
    def _check_filament_in_encoder(self):
        self._log_debug("Checking for filament in encoder...")
        if self._check_toolhead_sensor() == 1:
            self._log_debug("Filament must be in encoder because reported in extruder by toolhead sensor")
            return True
        self._servo_down()
        found = self._buzz_gear_motor()
        self._log_debug("Filament %s in encoder after buzzing gear motor" % ("detected" if found else "not detected"))
        return found

    # Return toolhead sensor or -1 if not installed
    def _check_toolhead_sensor(self):
        if self.toolhead_sensor != None:
            if self.toolhead_sensor.runout_helper.filament_present:
                self._log_trace("(Toolhead sensor detects filament)")
                return 1
            else:
                self._log_trace("(Toolhead sensor does not detect filament)")
                return 0
        return -1

    # Check for filament in extruder by moving extruder motor. This is only used with toolhead sensor
    # and can only happen is the short distance from sensor to gears. This check will eliminate that
    # problem and indicate if we can unload the rest of the bowden more quickly
    def _check_filament_stuck_in_extruder(self):
        self._log_debug("Checking for possibility of filament stuck in extruder gears...")
        self._set_above_min_temp()
        self._servo_up()
        delta = self._trace_filament_move("Checking extruder", -self.toolhead_homing_max, speed=25, motor="extruder")
        return (self.toolhead_homing_max - delta) > 1.


###########################
# FILAMENT LOAD FUNCTIONS #
###########################

    # Primary method to selects and loads tool. Assumes we are unloaded.
    def _select_and_load_tool(self, tool):
        self._log_debug('Loading tool T%d...' % tool)
        self._disable_encoder_sensor()
        self._select_tool(tool)
        gate = self._tool_to_gate(tool)
        if self.gate_status[gate] != self.GATE_AVAILABLE:
            raise ErcfError("Gate %d is empty!" % gate)
        self._load_sequence(self._get_calibration_ref())

    def _load_sequence(self, length, no_extruder = False):
        try:
            self._log_info("Loading filament...")
            self.filament_direction = self.DIRECTION_LOAD
            self._set_loaded_status(self.LOADED_STATUS_UNLOADED)
            # If full length load requested then assume homing is required (if configured)
            if (length >= self._get_calibration_ref()):
                if (length > self._get_calibration_ref()):
                    self._log_info("Restricting load length to extruder calibration reference of %.1fmm")
                    length = self._get_calibration_ref()
                home = True
            else:
                home = False

            self.toolhead.wait_moves()
            self._counter.reset_counts()    # Encoder 0000
            self._track_load_start()
            encoder_measured = self._load_encoder()
            if length - encoder_measured > 0:
                self._load_bowden(length - encoder_measured)
    
            if home:
                self._set_loaded_status(self.LOADED_STATUS_PARTIAL_END_OF_BOWDEN)
                self._log_debug("Full length load, will home filament...")
                skip_sync_move = False
                if self.home_to_extruder:
                    self._home_to_extruder(self.extruder_homing_max)
                if not no_extruder:
                    self._load_extruder(skip_sync_move)
    
            self.toolhead.wait_moves()
            self._log_info("Loaded %.1fmm of filament" % self._counter.get_distance())
            self._counter.reset_counts()    # Encoder 0000
        finally:
            self._track_load_end()

    # Load filament past encoder and return the actual measured distance detected by encoder
    def _load_encoder(self, retry=True):
        self._servo_down()
        self.filament_direction = self.DIRECTION_LOAD
        initial_encoder_position = self._counter.get_distance()
        delta = self._trace_filament_move("Initial load into encoder", self.LONG_MOVE_THRESHOLD)
        if (self.LONG_MOVE_THRESHOLD - delta) <= 6.0:
            if retry:
                self._log_always("Error unloading filament - not enough detected at encoder. Retrying...")
                self._servo_up()
                self._servo_down()
                delta = self._trace_filament_move("Retry load into encoder", self.LONG_MOVE_THRESHOLD)
                if (self.LONG_MOVE_THRESHOLD - delta) <= 6.0:
                    self._set_loaded_status(self.LOADED_STATUS_PARTIAL_BEFORE_ENCODER)
                    raise ErcfError("Error loading filament - not enough movement detected at encoder after retry")
            else:
                raise ErcfError("Error loading filament - not enough movement detected at encoder")

        self._set_loaded_status(self.LOADED_STATUS_PARTIAL_PAST_ENCODER)
        return self._counter.get_distance() - initial_encoder_position
    
    # Fast load of filament to approximate end of bowden (without homing)
    def _load_bowden(self, length):
        self._log_debug("Loading bowden tube")
        tolerance = self.load_bowden_tolerance
        self.filament_direction = self.DIRECTION_LOAD
        self._servo_down()

        # Fast load
        moves = 1 if length < (self._get_calibration_ref() / self.num_moves) else self.num_moves
        delta = 0
        for i in range(moves):
            msg = "Course loading move #%d into bowden" % (i+1)
            delta += self._trace_filament_move(msg, length / moves)
            if i < moves:
                self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_BOWDEN)

        # Correction attempts to load the filament according to encoder reporting
        if self.apply_bowden_correction and not self.calibrating:
            for i in range(2):
                if delta >= tolerance:
                    msg = "Correction load move #%d into bowden" % (i+1)
                    delta = self._trace_filament_move(msg, delta)
                    self._log_debug("Correction load move was necessary, encoder now measures %.1fmm" % self._counter.get_distance())
                else:
                    break
            if delta > tolerance:
                self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_BOWDEN)
                self._log_info("Warning: Excess slippage was detected in bowden tube load afer correction moves. Moved %.1fmm, Encoder delta %.1fmm. Possible causes:\nCalibration ref length too long (hitting extruder gear before homing) \nERCF gears are not properly gripping filament\nEncoder reading is inaccurate\nFaulty servo" % (length, delta))
                #raise ErcfError("Too much slippage (%.1fmm) detected during the load of bowden. Possible causes:\nCalibration ref length is too long\nERCF gears are not properly gripping filament\nEncoder reading is inaccurate\nFaulty servo" % delta)
        else:
            if delta >= tolerance:
                self._log_info("Warning: Excess slippage was detected in bowden tube load but 'apply_bowden_correction' is disabled. Moved %.1fmm, Encoder delta %.1fmm" % (length, delta))

    # This optional step snugs the filament up to the extruder gears.
    def _home_to_extruder(self, max_length):
        self._servo_down()
        self.filament_direction = self.DIRECTION_LOAD
        if self.homing_method == self.EXTRUDER_STALLGUARD:
            homed, measured_movement = self._home_to_extruder_with_stallguard(max_length)
        else:
            homed, measured_movement = self._home_to_extruder_collision_detection(max_length)
        if not homed:
            self._set_loaded_status(self.LOADED_STATUS_PARTIAL_END_OF_BOWDEN)
            raise ErcfError("Failed to reach extruder gear after moving %.1fmm" % max_length)
        if measured_movement > (max_length * 0.8):
            self._log_info("Warning: 80% of 'extruder_homing_max' was used homing. You may want to increase your initial load distance ('ercf_calib_ref' or increase 'extruder_homing_max'")
        self._set_loaded_status(self.LOADED_STATUS_PARTIAL_HOMED_EXTRUDER)
  
    def _home_to_extruder_collision_detection(self, max_length):
        step = self.extruder_homing_step
        self._log_debug("Homing to extruder gear, up to %.1fmm in %.1fmm steps" % (max_length, step))

        if self.tmc and self.extruder_homing_current < 100:
            gear_stepper_run_current = self.tmc.get_status(0)['run_current']
            self._log_debug("Temporarily reducing gear_stepper run current to %d%% for collision detection"
                                % self.extruder_homing_current)
            self.gcode.run_script_from_command("SET_TMC_CURRENT STEPPER=gear_stepper CURRENT=%.1f"
                                                % ((gear_stepper_run_current * self.extruder_homing_current)/100))

        initial_encoder_position = self._counter.get_distance()
        homed = False
        for i in range(int(max_length / step)):
            msg = "Homing step #%d" % (i+1)
            delta = self._trace_filament_move(msg, step, speed=5, accel=self.gear_homing_accel)
            measured_movement = self._counter.get_distance() - initial_encoder_position
            total_delta = step*(i+1) - measured_movement
            if delta >= step / 2. and total_delta >= step / 2.:
                # Not enough measured movement means we've hit the extruder
                homed = True
                break
        self._log_debug("Extruder %s found after %.1fmm move (%d steps), encoder measured %.1fmm (total_delta %.1fmm)"
                % ("not" if not homed else "", step*(i+1), i+1, measured_movement, total_delta))
        if self.tmc and self.extruder_homing_current < 100:
            self.gcode.run_script_from_command("SET_TMC_CURRENT STEPPER=gear_stepper CURRENT=%.1f" % gear_stepper_run_current)

        if total_delta > 5.0:
            self._log_info("Warning: A lot of slippage was detected whilst homing to extruder, you may want to reduce 'extruder_homing_current' and/or ensure a good grip on filament by gear drive")
        return homed, measured_movement

    # EXPERIMENTAL Note: not compatible with EASY BRD / or with sensorless selector homing (endstop contention)
    def _home_to_extruder_with_stallguard(self, max_length):
        self._log_debug("Homing to extruder gear with stallguard, up to %.1fmm" % max_length)
        initial_encoder_position = self._counter.get_distance()
        self._selector_stepper_move_wait(max_length, speed=5, homing_move=1)
        measured_movement = self._counter.get_distance() - initial_encoder_position
        if measured_movement < max_length:
            self._log_debug("Extruder entrance reached after %.1fmm" % measured_movement)
            homed = True
        else:
            homed = False
        return homed, measured_movement

    # This optional step aligns (homes) filament with the toolhead sensor. Returns measured movement
    def _home_to_sensor(self):
        # Strategy here is to home to the toolhead sensor which should be a very reliable location
        self._set_above_min_temp()
        sync = self.sync_load_length > 0
        step = self.toolhead_homing_step
        if self.toolhead_sensor.runout_helper.filament_present:
            # We shouldn't be here and probably means the toolhead sensor is malfunctioning/blocked
            raise ErcfError("Toolhead sensor malfunction - filament detected before it entered extruder!")
        if sync:
            self._set_above_min_temp()
            self._servo_down()
        else:
            self._servo_up()

        self._log_debug("Homing to toolhead sensor%s, up to %.1fmm in %.1fmm steps" % (" (synced)" if sync else "", self.toolhead_homing_max, step))
        for i in range(int(self.toolhead_homing_max / step)):
            msg = "Homing step #%d" % (i+1)
            delta = self._trace_filament_move(msg, step, speed=10, motor="both" if sync else "extruder")
            if self.toolhead_sensor.runout_helper.filament_present:
                self._log_debug("Toolhead sensor reached after %.1fmm (%d moves)" % (step*(i+1), i+1))                
                break

        if self.toolhead_sensor.runout_helper.filament_present:
            self._set_loaded_status(self.LOADED_STATUS_PARTIAL_HOMED_SENSOR)
        else:
            self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_EXTRUDER)
            raise ErcfError("Failed to reach toolhead sensor after moving %.1fmm" % self.toolhead_homing_max)

    # Move filament from the extruder entrance to the nozzle. Return measured movement
    def _load_extruder(self, skip_sync_move=False):
        self.filament_direction = self.DIRECTION_LOAD
        self._set_above_min_temp()

        # With toolhead sensor we must home first
        if self.toolhead_sensor != None:
            self._home_to_sensor()
            skip_sync_move = True

        length = self.home_position_to_nozzle
        self._log_debug("Loading last %.1fmm to the nozzle..." % length)
        initial_encoder_position = self._counter.get_distance()

        # Sync load (ERCF + extruder) for passing over control from gear stepper to extruder
        # Not strictly necessary with home to extruder option but will still increase reliability
        # This will automatically be skipped if we are homed to toolhead sensor
        if not skip_sync_move and self.sync_load_length > 0:
            self._servo_down()
            self._log_debug("Moving the gear and extruder motors in sync for %.1fmm" % self.sync_load_length) 
            delta = self._trace_filament_move("Sync load move", self.sync_load_length, speed=10, motor="both")
            tolerance = max(self.sync_load_length * 0.3, 4.0) # Allow around 30% of slippage because of possible spring in filament
            if delta > tolerance:
                raise ErcfError("Too much slippage detected during the sync load to nozzle")
            length -= (self.sync_load_length - delta)
        elif self.home_to_extruder and self.delay_servo_release > 0:
            # Delay servo release by a few mm to keep filamanet tension for reliable transition
            delta = self._trace_filament_move("Small extruder move under filament tension before servo release", self.delay_servo_release, speed=20, motor="extruder")
            length -= self.delay_servo_release

        # Move the remaining distance to the nozzle meltzone under exclusive extruder stepper control
        self._servo_up()
        delta = self._trace_filament_move("Remainder of final move to meltzone", length, speed=20, motor="extruder")

        # Final sanity check
        measured_movement = self._counter.get_distance() - initial_encoder_position
        total_delta = self.home_position_to_nozzle - measured_movement
        self._log_debug("Total measured movement: %.1fmm, total delta: %.1fmm" % (measured_movement, total_delta))
        if total_delta > (length * 0.80):   # 80% of final move length
            raise ErcfError("Move to nozzle failed (encoder not sensing sufficent movement). Extruder may not have picked up filament")

        self._set_loaded_status(self.LOADED_STATUS_FULL)
        self._log_info('ERCF load successful')


#############################
# FILAMENT UNLOAD FUNCTIONS #
#############################

    # Primary method to unload current tool but retains selection
    def _unload_tool(self, in_print=False):
        if self._check_is_paused(): return
        if self.loaded_status == self.LOADED_STATUS_UNLOADED:
            self._log_debug("Tool already unloaded")
            return
        self._log_debug("Unloading tool %s" % self._selected_tool_string())
        self._disable_encoder_sensor()
        self._unload_sequence(self._get_calibration_ref(), skip_tip=in_print)

    def _unload_sequence(self, length, check_state=False, skip_sync_move=False, skip_tip=False):
        try:
            self._log_info("Unloading filament...")
            self.filament_direction = self.DIRECTION_UNLOAD
            self.toolhead.wait_moves()
            self._counter.reset_counts()    # Encoder 0000
            self._track_unload_start()

            if check_state or self.loaded_status == self.LOADED_STATUS_UNKNOWN:
                # Let's determine where filament is and reset state before continuing
                self._log_debug("Unknown filament postion, recovering state...")
                self._recover_loaded_state()
            else:
                self._display_visual_state()

            if self.loaded_status == self.LOADED_STATUS_UNLOADED:
                self._log_info("Filament already ejected")
                self._servo_up()
                return

            # Check for cases where we must form tip
            if not skip_tip and self.loaded_status >= self.LOADED_STATUS_PARTIAL_IN_EXTRUDER:
                if self._form_tip_standalone():
                    # Definitely now just in extruder
                    self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_EXTRUDER)
                else:
                    # No movement means we can safely assume we are somewhere in the bowden
                    self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_BOWDEN)
     
            if self.loaded_status >= self.LOADED_STATUS_PARTIAL_IN_EXTRUDER:
                # Unload extruder, then fast unload of bowden
                self._unload_extruder()
                self._unload_bowden(length - self.unload_buffer, skip_sync_move=skip_sync_move)
                self._unload_encoder(self.unload_buffer)
            elif self.loaded_status == self.LOADED_STATUS_PARTIAL_END_OF_BOWDEN:
                # Fast unload of bowden
                self._unload_bowden(length - self.unload_buffer, skip_sync_move=skip_sync_move)
                self._unload_encoder(self.unload_buffer)
            elif self.loaded_status == self.LOADED_STATUS_PARTIAL_IN_BOWDEN:
                # Have to do slow unload because we don't know exactly where we are
                self._unload_encoder(length)
            else:
                self._log_debug("Assertion failure - unexpected state %d in _unload_sequence()" % self.loaded_status)
                raise ErcfError("Unexpected state during unload sequence")

            self._servo_up()
            self.toolhead.wait_moves()
            self._log_info("Unloaded %.1fmm of filament" % self._counter.get_distance())
            self._counter.reset_counts()    # Encoder 0000

        finally:
            self._track_unload_end()

    # This is a recovery routine to determine the most conservate location of the filament for unload purposes
    def _recover_loaded_state(self):
        toolhead_sensor_state = self._check_toolhead_sensor()
        if toolhead_sensor_state == -1:     # Not installed
            if self._check_filament_in_encoder():
                self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_EXTRUDER)
            else:
                self._set_loaded_status(self.LOADED_STATUS_UNLOADED)
        elif toolhead_sensor_state == 1:    # Filament detected in toolhead
            self._set_loaded_status(self.LOADED_STATUS_FULL)
        else:                               # Filament not detected in toolhead
            if self._check_filament_in_encoder():
                if not self._check_filament_stuck_in_extruder():
                    self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_BOWDEN) # This prevents fast unload move
                else:
                    self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_EXTRUDER)
            else:
                self._set_loaded_status(self.LOADED_STATUS_UNLOADED)

    # Extract filament past extruder gear (end of bowden)
    # Assume that tip has already been formed and we are parked somewhere in the encoder either by
    # slicer or my stand alone tip creation
    def _unload_extruder(self):
        self._log_debug("Extracting filament from extruder")
        self.filament_direction = self.DIRECTION_UNLOAD
        self._set_above_min_temp()
        self._servo_up()

        # Goal is to exit extruder. Two strategies depending on availability of toolhead sensor
        # Back up 15mm at a time until either the encoder doesnt see any movement or toolhead sensor reports clear
        # Do this until we have travelled more than the length of the extruder 
        max_length = self.home_position_to_nozzle + self.toolhead_homing_max + 10.
        step = self.encoder_move_step_size
        self._log_debug("Trying to exit the extruder, up to %.1fmm in %.1fmm steps" % (max_length, step))
        out_of_extruder = False
        speed = 10  # First pull slower in case of no tip
        for i in range(int(max_length / self.encoder_move_step_size)):
            msg = "Step #%d:" % (i+1)
            delta = self._trace_filament_move(msg, -self.encoder_move_step_size, speed=speed, motor="extruder")
            speed = 25  # Can pull faster on subsequent steps

            if self.toolhead_sensor != None:
                if not self.toolhead_sensor.runout_helper.filament_present:
                    self._set_loaded_status(self.LOADED_STATUS_PARTIAL_HOMED_SENSOR)
                    self._log_debug("Toolhead sensor reached after %d moves" % (i+1))                
                    # Last move to ensure we are really free because of small space between sensor and gears
                    delta = self._trace_filament_move("Last sanity move", -self.toolhead_homing_max, speed=speed, motor="extruder")
                    out_of_extruder = True
                    break
            else:
                if (self.encoder_move_step_size - delta) <= 1.0:
                    self._log_debug("Extruder entrance reached after %d moves" % (i+1))                
                    out_of_extruder = True
                    break

        if not out_of_extruder:
            self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_EXTRUDER)
            raise ErcfError("Filament seems to be stuck in the extruder")

        self._log_debug("Filament should be out of extruder")
        self._set_loaded_status(self.LOADED_STATUS_PARTIAL_END_OF_BOWDEN)

    # Fast unload of filament from exit of extruder gear (end of bowden) to close to ERCF (but still in encoder)
    def _unload_bowden(self, length, skip_sync_move=False):
        self._log_debug("Unloading bowden tube")
        self.filament_direction = self.DIRECTION_UNLOAD
        tolerance = self.unload_bowden_tolerance
        self._servo_down()

        # Initial short move allows for dealing with (servo) errors. If synchronized it can help with hair pull
        if not self.calibrating:
            sync = not skip_sync_move and self.sync_unload_length > 0
            initial_move = 10. if not sync else self.sync_unload_length
            if sync:
                self._log_debug("Moving the gear and extruder motors in sync for %.1fmm" % -initial_move) 
                delta = self._trace_filament_move("Sync unload", -initial_move, speed=10, motor="both")
            else:
                self._log_debug("Moving the gear motor for %.1fmm" % -initial_move) 
                delta = self._trace_filament_move("Unload", -initial_move, speed=10, motor="gear")
            if delta > initial_move / 2:
                self._log_always("Error unloading filament - not enough detected at encoder. Suspect servo not properly down")
                self._log_always("Adjusting 'extra_servo_dwell_down' may help. Retrying...")
                self._servo_up()
                self._servo_down()
                if sync:
                    delta = self._trace_filament_move("Retrying sync unload move after servo reset", -delta, speed=10, motor="both")
                else:
                    delta = self._trace_filament_move("Retrying unload move after servo reset", -delta, speed=10, motor="gear")
                if delta > 2.0:
                    # Actually we are likely still stuck in extruder
                    self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_EXTRUDER)
                    raise ErcfError("Too much slippage (%.1fmm) detected during the sync unload from extruder" % delta)
                length -= (initial_move - delta)
        
        # Continue fast unload
        moves = 1 if length < (self._get_calibration_ref() / self.num_moves) else self.num_moves
        delta = 0
        for i in range(moves):
            msg = "Course unloading move #%d from bowden" % (i+1)
            delta += self._trace_filament_move(msg, -length / moves)
            if i < moves:
                self._set_loaded_status(self.LOADED_STATUS_PARTIAL_IN_BOWDEN)

        if delta >= tolerance:
            # Only a warning because _unload_encoder() will deal with it
            self._log_info("Warning: Excess slippage was detected in bowden tube unload. Moved %.1fmm, Encoder delta %.1fmm" % (length, delta))

        self._set_loaded_status(self.LOADED_STATUS_PARTIAL_PAST_ENCODER)

    # Step extract of filament from encoder to ERCF park position
    def _unload_encoder(self, max_length):
        self._log_debug("Slow unload of the encoder")
        self.filament_direction = self.DIRECTION_UNLOAD
        max_steps = int(max_length / self.encoder_move_step_size) + 5
        self._servo_down()
        for i in range(max_steps):
            msg = "Unloading step #%d from encoder" % (i+1)
            delta = self._trace_filament_move(msg, -self.encoder_move_step_size)
            if delta >= 3.0:
                # Large enough delta here means we are out of the encoder
                self._set_loaded_status(self.LOADED_STATUS_PARTIAL_BEFORE_ENCODER)
                park = self.parking_distance - delta
                delta = self._trace_filament_move("Final parking", -park)
                # We don't expect any movement of the encoder, but a hair may cause a slight reading
                if (park - delta) < 5.0:
                    self._set_loaded_status(self.LOADED_STATUS_UNLOADED)
                    return
        raise ErcfError("Unable to get the filament out of the encoder cart")

    # Form tip and return True if encoder movement occured
    def _form_tip_standalone(self):
        park_pos = 35.  # TODO bring in from tip forming (parking postion in extruder)
        self._log_info("Forming tip...")
        self._set_above_min_temp()
        self._servo_up()
        initial_encoder_position = self._counter.get_distance()
        self.gcode.run_script_from_command("_ERCF_FORM_TIP_STANDALONE")
        delta = self._counter.get_distance() - initial_encoder_position
        self._log_trace("After tip formation, encoder moved %.2f" % delta)
        self._counter.set_distance(initial_encoder_position + park_pos)
        return delta > 0.0


#################################################
# TOOL SELECTION AND SELECTOR CONTROL FUNCTIONS #
#################################################

    def _home(self, tool = -1):
        if self._get_calibration_version() != 3:
            self._log_info("You are running an old calibration version.\nIt is strongly recommended that you rerun 'ERCF_CALIBRATE_SINGLE TOOL=0' to generate an updated calibration value")

        self._log_info("Homing ERCF...")
        if self.is_paused:
            self._log_debug("ERCF is locked, unlocking it before continuing...")
            self._unlock()

        self._disable_encoder_sensor()
        if not self.loaded_status == self.LOADED_STATUS_UNLOADED:
            self._unload_sequence(self._get_calibration_ref(), check_state=True)
        self._unselect_tool()
        if self._home_selector():
            if tool >= 0:
                self._select_tool(tool)

    def _home_selector(self):
        self.is_homed = False
        self._servo_up()
        num_channels = len(self.selector_offsets)
        selector_length = 10. + (num_channels-1)*21. + ((num_channels-1)//3)*5. + (self.bypass_offset > 0)
        self._log_debug("Moving up to %.1fmm to home a %d channel ERCF" % (selector_length, num_channels))
        self.toolhead.wait_moves()
        if self.sensorless_selector == 1:
            self.selector_stepper.do_set_position(0.)
            self._selector_stepper_move_wait(5, False)  # Ensure some bump space
            self.selector_stepper.do_set_position(0.)
            self._selector_stepper_move_wait(-selector_length, speed=60, homing_move=1)
            # Did we actually hit the physical endstop (configured on gear_stepper!)
            self.is_homed = self.gear_endstop.query_endstop(self.toolhead.get_last_move_time())
        else:
            self.selector_stepper.do_set_position(0.)
            self._selector_stepper_move_wait(-selector_length, speed=100, homing_move=1)   # Fast homing move
            self.selector_stepper.do_set_position(0.)
            self._selector_stepper_move_wait(5, False)                      # Ensure some bump space
            self._selector_stepper_move_wait(-10, speed=10, homing_move=1)  # Slower more accurate  homing move
            self.is_homed = self.selector_endstop.query_endstop(self.toolhead.get_last_move_time())

        if not self.is_homed:
            self._set_tool_selected(self.TOOL_UNKNOWN)
            raise ErcfError("Homing selector failed because of blockage")
        else:
            self.selector_stepper.do_set_position(0.)     

        return self.is_homed

    def _move_selector_sensorless(self, target):
        successful, travel = self._attempt_selector_move(target)
        if not successful:
            if abs(travel) <= 3.0 :         # Filament stuck in the current selector
                self._log_info("Selector is blocked by inside filament, trying to recover...")
                # Realign selector
                self.selector_stepper.do_set_position(0.)
                self._log_trace("Resetting selector by a distance of: %.1fmm" % -travel)
                self._selector_stepper_move_wait(-travel)
                
                # See if we can detect filament in the encoder
                self._servo_down()
                found = self._buzz_gear_motor()
                if not found:
                    # Try to engage filament to the encoder
                    delta = self._trace_filament_move("Trying to re-enguage encoder", 45.)
                    if delta == 45.:    # No movement
                        # Could not reach encoder
                        raise ErcfError("Selector recovery failed. Path is probably internally blocked and unable to move filament to clear")

                # Now try a full unload sequence
                try:
                    self._unload_sequence(self._get_calibration_ref(), check_state=True)
                except ErcfError as ee:
                    # Add some more context to the error and re-raise
                    raise ErcfError("Selector recovery failed because: %s" % (tool, ee.message))
                
                # Ok, now check if selector can now reach proper target
                self._home_selector()
                successful, travel = self._attempt_selector_move(target)
                if not successful:
                    # Selector path is still blocked
                    self.is_homed = False
                    self._unselect_tool()
                    raise ErcfError("Selector recovery failed. Path is probably internally blocked")
            else :                          # Selector path is blocked, probably not internally
                self.is_homed = False
                self._unselect_tool()
                raise ErcfError("Selector path is probably externally blocked")

    def _attempt_selector_move(self, target):
        selector_steps = self.selector_stepper.steppers[0].get_step_dist()
        init_position = self.selector_stepper.get_position()[0]
        init_mcu_pos = self.selector_stepper.steppers[0].get_mcu_position()
        target_move = target - init_position
        self._selector_stepper_move_wait(target, homing_move=2)  # Home sensing move
        mcu_position = self.selector_stepper.steppers[0].get_mcu_position()
        travel = (mcu_position - init_mcu_pos) * selector_steps
        delta = abs(target_move - travel)
        self._log_trace("Selector moved %.1fmm of intended travel from: %.1fmm to: %.1fmm (delta: %.1fmm)"
                        % (travel, init_position, target, delta))
        if delta <= 1.0 :
            # True up position
            self._log_trace("Truing selector %.1fmm to %.1fmm" % (delta, target))
            self.selector_stepper.do_set_position(init_position + travel)
            self._selector_stepper_move_wait(target)
            return True, travel
        else:
            return False, travel

    # This is the main function for initiating a tool change, handling unload if necessary
    def _change_tool(self, tool, in_print=True):
        self._log_debug("%s tool change initiated" % ("In print" if in_print else "Standalone"))
        skip_unload = False
        initial_tool_string = "unknown" if self.tool_selected < 0 else ("T%d" % self.tool_selected)
        if tool == self.tool_selected and self.loaded_status == self.LOADED_STATUS_FULL:
                self._log_always("Tool T%d is already ready" % tool)
                return
        if self.loaded_status == self.LOADED_STATUS_UNLOADED:
            skip_unload = True
            msg = "Tool change requested, to T%d" % tool
            self.gcode.run_script_from_command("M117 -> T%d" % tool)
        else:
            msg = "Tool change requested, from %s to T%d" % (initial_tool_string, tool)
            self.gcode.run_script_from_command("M117 %s -> T%d" % (initial_tool_string, tool))
        # Important to always inform user in case there is an error and manual recovery is necessary
        self._log_always(msg)

        # Identify the start up use case and make it easy for user
        if not self.is_homed and self.tool_selected == self.TOOL_UNKNOWN:
            self._log_info("ERCF not homed, homing it before continuing...")
            self._home(tool)
            skip_unload = True

        if not skip_unload:
            self._unload_tool(in_print)
        self._select_and_load_tool(tool)

        if self.enable_clog_detection and in_print:
            self._enable_encoder_sensor()
        self._track_swap_completed()
        self._dump_statistics()

    def _unselect_tool(self):
        self._servo_up()
        self._set_tool_selected(self.TOOL_UNKNOWN, silent=True)

    def _select_tool(self, tool):
        if tool == self.tool_selected: return
        if tool < 0 or tool >= len(self.selector_offsets):
            self._log_always("Tool %d does not exist" % tool)
            return

        self._log_debug("Selecting tool T%d on gate #%d..." % (tool, self._tool_to_gate(tool)))
        self._select_gate(self._tool_to_gate(tool))
        self._set_tool_selected(tool, silent=True)
        self._log_info("Tool T%d enabled" % tool)

    def _select_gate(self, gate):
        self._servo_up()
        offset = self.selector_offsets[gate]
        if self.sensorless_selector == 1:
            self._move_selector_sensorless(offset)
        else:
            self._selector_stepper_move_wait(offset)

    def _select_bypass(self):
        if self.tool_selected == self.TOOL_BYPASS: return
        if self.bypass_offset == 0:
            self._log_always("Bypass not configured")
            return

        self._log_info("Selecting filament bypass...")
        self._servo_up()
        if self.sensorless_selector == 1:
            self._move_selector_sensorless(self.bypass_offset)
        else:
            self._selector_stepper_move_wait(self.bypass_offset)
        self.filament_direction = self.DIRECTION_LOAD
        self._set_tool_selected(self.TOOL_BYPASS)
        self._log_info("Bypass enabled")

    def _set_tool_selected(self, tool, silent=False):
            self.tool_selected = tool
            if tool == self.TOOL_UNKNOWN or tool == self.TOOL_BYPASS:
                self.gate_selected = self.GATE_UNKNOWN
                self._set_steps(1.)
            else:
                self.gate_selected = self._tool_to_gate(tool)
                self._set_steps(self._get_gate_ratio(self._tool_to_gate(tool)))
            if not silent:
                self._display_visual_state()

    # Note that rotational steps are set in the above tool selection or calibration functions
    def _set_steps(self, ratio=1.):
        self._log_trace("Setting ERCF gear motor step ratio to %.6f" % ratio)
        new_step_dist = self.ref_step_dist / ratio
        stepper = self.gear_stepper.steppers[0]
        if hasattr(stepper, "set_rotation_distance"):
            new_rotation_dist = new_step_dist * stepper.get_rotation_distance()[1]
            stepper.set_rotation_distance(new_rotation_dist)
        else:
            # Backwards compatibility for old klipper versions
            stepper.set_step_dist(new_step_dist)


### CORE GOCDE COMMMANDS ##########################################################

    cmd_ERCF_UNLOCK_help = "Unlock ERCF operations"
    def cmd_ERCF_UNLOCK(self, gcmd):        
        self._log_info("Unlocking the ERCF")
        self._unlock()
        self._log_info("Refer to the manual before resuming the print")

    cmd_ERCF_HOME_help = "Home the ERCF"
    def cmd_ERCF_HOME(self, gcmd):
        tool = gcmd.get_int('TOOL', 0, minval=0, maxval=len(self.selector_offsets)-1)
        try:
            self._home(tool)
        except ErcfError as ee:
            self._pause(ee.message)

    cmd_ERCF_SELECT_TOOL_help = "Select the specified tool"
    def cmd_ERCF_SELECT_TOOL(self, gcmd):
        if self._check_is_paused(): return
        if self._check_not_homed(): return
        if self._check_is_loaded(): return
        tool = gcmd.get_int('TOOL', 0, minval=0, maxval=len(self.selector_offsets)-1)
        try:
            self._select_tool(tool)
        except ErcfError as ee:
            self._pause(ee.message)

    cmd_ERCF_CHANGE_TOOL_help = "Perform a tool swap"
    def cmd_ERCF_CHANGE_TOOL(self, gcmd):
        if self._check_is_paused(): return
        if self._check_in_bypass(): return
        tool = gcmd.get_int('TOOL', 0, minval=0, maxval=len(self.selector_offsets)-1)
        standalone = gcmd.get_int('STANDALONE', 0, minval=0, maxval=1)
        in_print = self._is_in_print() and (standalone == 0)
        try:
            self._change_tool(tool, in_print)
        except ErcfError as ee:
            self._pause(ee.message)

    cmd_ERCF_EJECT_help = "Eject filament and park it in the ERCF"
    def cmd_ERCF_EJECT(self, gcmd):
        if self._check_is_paused(): return
        if self._check_in_bypass(): return
        try:
            self._unload_tool()
        except ErcfError as ee:
            self._pause(ee.message)

    cmd_ERCF_SELECT_BYPASS_help = "Select the filament bypass"
    def cmd_ERCF_SELECT_BYPASS(self, gcmd):
        if self._check_is_paused(): return
        if self._check_not_homed(): return
        if self._check_is_loaded(): return
        try:
            self._select_bypass()
        except ErcfError as ee:
            self._pause(ee.message)

    cmd_ERCF_LOAD_BYPASS_help = "Smart load of filament from end of bowden (gears) to nozzle. Designed for bypass usage"
    def cmd_ERCF_LOAD_BYPASS(self, gcmd):
        if self._check_is_paused(): return
        if self._check_not_homed(): return
        try:
            self._load_extruder(True, skip_sync_move=True)
        except ErcfError as ee:
            self._pause(ee.message)

    cmd_ERCF_PAUSE_help = "Pause the current print and lock the ERCF operations"
    def cmd_ERCF_PAUSE(self, gcmd):
        if self._check_is_paused(): return
        self._pause("Pause macro was directly called")

    cmd_ERCF_RECOVER_help = "Recover the filament location state after manual intervention/movement"
    def cmd_ERCF_RECOVER(self, gcmd):
        if self._check_is_paused(): return
        self._log_info("Recovering filament position...")
        self._recover_loaded_state()


### GOCDE COMMMANDS INTENDED FOR TESTING #####################################

    cmd_ERCF_TEST_GRIP_help = "Test the ERCF grip for a Tool"
    def cmd_ERCF_TEST_GRIP(self, gcmd):
        if self._check_is_paused(): return
        self._servo_down()
        self.cmd_ERCF_MOTORS_OFF(gcmd)

    cmd_ERCF_TEST_SERVO_help = "Test the servo angle"
    def cmd_ERCF_TEST_SERVO(self, gcmd):
        if self._check_is_paused(): return
        angle = gcmd.get_float('VALUE')
        self._log_debug("Setting servo to angle: %d" % angle)
        self._servo_set_angle(angle)
        self.toolhead.dwell(0.25 + self.extra_servo_dwell_up / 1000.)
        self._servo_off()

    cmd_ERCF_TEST_MOVE_GEAR_help = "Move the ERCF gear"
    def cmd_ERCF_TEST_MOVE_GEAR(self, gcmd):
        if self._check_is_paused(): return
        length = gcmd.get_float('LENGTH', 200.)
        speed = gcmd.get_float('SPEED', 50.)
        accel = gcmd.get_float('ACCEL', 200.)
        self._gear_stepper_move_wait(length, wait=False, speed=speed, accel=accel)

    cmd_ERCF_TEST_LOAD_SEQUENCE_help = "Test sequence"
    def cmd_ERCF_TEST_LOAD_SEQUENCE(self, gcmd):
        if self._check_is_paused(): return
        if self._check_in_bypass(): return
        if self._check_not_homed(): return
        self._disable_encoder_sensor()
        loops = gcmd.get_int('LOOP', 10)
        random = gcmd.get_int('RANDOM', 0)
        to_nozzle = gcmd.get_int('FULL', 0)
        try:
            for l in range(loops):
                self._log_always("Testing loop %d / %d" % (l, loops))
                for t in range(len(self.selector_offsets)):
                    tool = t
                    if random == 1:
                        tool = randint(0, len(self.selector_offsets)-1)
                    gate = self._tool_to_gate(tool)
                    if self.gate_status[gate] != self.GATE_AVAILABLE:
                        self._log_always("Skipping tool %d of %d because gate %d is empty" % (tool, len(self.selector_offsets), gate))
                    else:
                        self._log_always("Testing tool %d of %d (gate %d)" % (tool, len(self.selector_offsets), gate))
                        if not to_nozzle:
                            self._select_tool(tool)
                            self._load_sequence(100, no_extruder=True)
                            self._unload_sequence(100, skip_sync_move=True)
                        else:
                            self._select_and_load_tool(tool)
                            self._unload_tool()
            self._select_tool(0)
        except ErcfError as ee:
            self._pause(ee.message)

    cmd_ERCF_TEST_LOAD_help = "Test loading of filament from ERCF to the extruder"
    def cmd_ERCF_TEST_LOAD(self, gcmd):
        if self._check_is_paused(): return
        if self._check_in_bypass(): return
        if self._check_is_loaded(): return
        self._disable_encoder_sensor()
        length = gcmd.get_float('LENGTH', 100.)
        try:
            self._load_sequence(length, no_extruder=True)
        except ErcfError as ee:
            self._log_always("Load test failed: %s" % ee.message)

    cmd_ERCF_TEST_TRACKING_help = "Test the tracking of gear feed and encoder sensing"
    def cmd_ERCF_TEST_TRACKING(self, gcmd):
        if self._check_is_paused(): return
        if self._check_in_bypass(): return
        direction = gcmd.get_int('DIRECTION', 1, minval=-1, maxval=1)
        step = gcmd.get_float('STEP', 1, minval=0.5, maxval=20)
        if direction == 0: return
        self._disable_encoder_sensor()
        try:
            if not self._is_filament_in_bowden():
                # Ready ERCF for test if not already setup
                self._unload_tool()
                self._load_sequence(100 if direction == 1 else 200, no_extruder=True)
            self._counter.reset_counts()    # Encoder 0000
            for i in range(1, int(100 / step)):
                delta = self._trace_filament_move("Test move", direction * step)
                measured = self._counter.get_distance()
                moved = i * step
                if (moved - measured) >= 1.0:
                    drift = "+++++!!"[0:int(moved - measured)]
                elif (moved - measured) <= -1.0:
                    drift = "-----!!"[0:int(measured - moved)]
                else:
                    drift = ""
                self._log_info("Gear/Encoder : %05.2f / %05.2f mm %s" % (moved, measured, drift))
            self._unload_tool()
        except ErcfError as ee:
            self._log_always("Tracking test failed: %s" % ee.message)
    
    cmd_ERCF_TEST_UNLOAD_help = "For testing for fine control of filament unloading and parking it in the ERCF"
    def cmd_ERCF_TEST_UNLOAD(self, gcmd):
        if self._check_is_paused(): return
        if self._check_in_bypass(): return
        unknown_state = gcmd.get_int('UNKNOWN', 0, minval=0, maxval=1)
        length = gcmd.get_float('LENGTH', self._get_calibration_ref())
        try:
            self._unload_sequence(length, check_state=unknown_state, skip_sync_move=True)
        except ErcfError as ee:
            self._log_always("Unload test failed: %s" % ee.message)

    cmd_ERCF_TEST_HOME_TO_EXTRUDER_help = "Test homing the filament to the extruder from the end of the bowden. Intended to be used for calibrating the current reduction or stallguard threshold"
    def cmd_ERCF_TEST_HOME_TO_EXTRUDER(self, params):
        if self._check_is_paused(): return
        if self._check_in_bypass(): return
        restore = params.get_int('RETURN', 0, minval=0, maxval=1)
        try:
            self.toolhead.wait_moves() 
            initial_encoder_position = self._counter.get_distance()
            self._home_to_extruder(self.extruder_homing_max)
            measured_movement = self._counter.get_distance() - initial_encoder_position
            spring = self._servo_up()
            self._log_info("Filament homed to extruder, encoder measured %.1fmm" % measured_movement)
            self._log_info("Filament sprung back %.1fmm when servo released" % spring)
            if restore:
                self._servo_down()
                self._log_debug("Returning filament %.1fmm to original position after homing test" % -(measured_movement - spring))
                self._gear_stepper_move_wait(-(measured_movement - spring))
        except ErcfError as ee:
            self._log_always("Homing test failed: %s" % ee.message)

    cmd_ERCF_TEST_CONFIG_help = "Runtime adjustment of ERCF configuration for testing purposes"
    def cmd_ERCF_TEST_CONFIG(self, gcmd):
        self.long_moves_speed = gcmd.get_float('LONG_MOVES_SPEED', self.long_moves_speed, above=20.)
        self.short_moves_speed = gcmd.get_float('SHORT_MOVES_SPEED', self.short_moves_speed, above=20.)
        self.home_to_extruder = gcmd.get_int('HOME_TO_EXTRUDER', self.home_to_extruder, minval=0, maxval=1)
        self.extruder_homing_max = gcmd.get_float('EXTRUDER_HOMING_MAX', self.extruder_homing_max, above=20.)
        self.extruder_homing_step = gcmd.get_float('EXTRUDER_HOMING_STEP', self.extruder_homing_step, minval=1., maxval=5.)
        self.extruder_homing_current = gcmd.get_int('EXTRUDER_HOMING_CURRENT', self.extruder_homing_current, minval=0, maxval=100)
        if self.extruder_homing_current == 0: self.extruder_homing_current = 100
        self.toolhead_homing_max = gcmd.get_float('TOOLHEAD_HOMING_MAX', self.toolhead_homing_max, minval=0.)
        self.toolhead_homing_step = gcmd.get_float('TOOLHEAD_HOMING_STEP', self.toolhead_homing_step, minval=0.5, maxval=5.)
        self.delay_servo_release = gcmd.get_float('DELAY_SERVO_RELEASE', self.delay_servo_release, minval=0., maxval=5.)
        self.sync_load_length = gcmd.get_float('SYNC_LOAD_LENGTH', self.sync_load_length, minval=0., maxval=100.)
        self.sync_unload_length = gcmd.get_float('SYNC_UNLOAD_LENGTH', self.sync_unload_length, minval=0., maxval=100.)
        self.num_moves = gcmd.get_int('NUM_MOVES', self.num_moves, minval=1)
        self.apply_bowden_correction = gcmd.get_int('APPLY_BOWDEN_CORRECTION', self.apply_bowden_correction, minval=0, maxval=1)
        self.load_bowden_tolerance = gcmd.get_float('LOAD_BOWDEN_TOLERANCE', self.load_bowden_tolerance, minval=1., maxval=50.)
        self.home_position_to_nozzle = gcmd.get_float('HOME_POSITION_TO_NOZZLE', self.home_position_to_nozzle, minval=25.)
        self.variables['ercf_calib_ref'] = gcmd.get_float('ERCF_CALIB_REF', self.variables['ercf_calib_ref'], minval=10.)
        self.variables['ercf_calib_clog_length'] = gcmd.get_float('ERCF_CALIB_CLOG_LENGTH', self.variables['ercf_calib_clog_length'], minval=1., maxval=100.)
        msg = "long_moves_speed = %.1f" % self.long_moves_speed
        msg += "\nshort_moves_speed = %.1f" % self.short_moves_speed
        msg += "\nhome_to_extruder = %d" % self.home_to_extruder
        msg += "\nextruder_homing_max = %.1f" % self.extruder_homing_max
        msg += "\nextruder_homing_step = %.1f" % self.extruder_homing_step
        msg += "\nextruder_homing_current = %d" % self.extruder_homing_current
        msg += "\ntoolhead_homing_max = %.1f" % self.toolhead_homing_max
        msg += "\ntoolhead_homing_step = %.1f" % self.toolhead_homing_step
        msg += "\ndelay_servo_release = %.1f" % self.delay_servo_release
        msg += "\nsync_load_length = %.1f" % self.sync_load_length
        msg += "\nsync_unload_length = %.1f" % self.sync_unload_length
        msg += "\nnum_moves = %d" % self.num_moves
        msg += "\napply_bowden_correction = %d" % self.apply_bowden_correction
        msg += "\nload_bowden_tolerance = %d" % self.load_bowden_tolerance
        msg += "\nhome_position_to_nozzle = %.1f" % self.home_position_to_nozzle
        msg += "\nercf_calib_ref = %.1f" % self.variables['ercf_calib_ref']
        msg += "\nercf_calib_clog_length = %.1f" % self.variables['ercf_calib_clog_length']
        self._log_info(msg)


###########################################
# RUNOUT, ENDLESS SPOOL and GATE HANDLING #
###########################################

    def _handle_runout(self):
        if self._check_is_paused(): return
        if self.tool_selected < 0:
            raise ErcfError("Filament runout or movement issue on an unknown or bypass tool - manual intervention is required")

        self._log_info("Issue on tool T%d" % self.tool_selected)
        self._log_debug("Checking if this is a clog or a runout...")
        self._disable_encoder_sensor()
        self._counter.reset_counts()    # Encoder 0000

        # Check for clog by looking for filament in the encoder
        self._servo_down()
        found = self._buzz_gear_motor()
        self._servo_up()
        if found:
            raise ErcfError("A clog has been detected and requires manual intervention")

        # We have a filament runout
        self._log_always("A runout has been detected")
        if self.enable_endless_spool:
            # Need to capture PA just in case user's tip forming resets it
            initial_pa = self.printer.lookup_object("extruder").get_status(0)['pressure_advance']
            group = self.endless_spool_groups[self.tool_selected]
            self._log_info("EndlessSpool checking for additional spools in group %d..." % group)
            num_tools = len(self.selector_offsets)
            self._remap_tool(self.tool_selected, self.gate_selected, 0) # Indicate current gate is empty
            next_gate = -1
            check = self.gate_selected + 1
            while check != self.gate_selected:
                check = check % num_tools
                if self.endless_spool_groups[check] == group and self.gate_status[check] == self.GATE_AVAILABLE:
                    next_gate = check
                    break
                check += 1
            if next_gate == -1:
                self.gate_selected = self.GATE_UNKNOWN
                self._log_info("No more available spools found in group %d - manual intervention is required" % self.endless_spool_groups[self.tool_selected])
                self._log_info(self._tool_to_gate_map_to_human_string())
                raise ErcfError("No more available EndlessSpool spools available")
            self._log_info("Remapping T%d to gate #%d" % (self.tool_selected, next_gate))

            self.gcode.run_script_from_command("SAVE_GCODE_STATE NAME=ERCF_PRE_UNLOAD")
            self.gcode.run_script_from_command("_ERCF_ENDLESS_SPOOL_PRE_UNLOAD")
            if not self._form_tip_standalone():
                self._log_debug("Didn't detect filamanet during tip forming move!")
            self._unload_tool(in_print=True)
            self._remap_tool(self.tool_selected, next_gate, 1)
            self.gate_selected = next_gate
            self._select_and_load_tool(tool)
            self.gcode.run_script_from_command("SET_PRESSURE_ADVANCE ADVANCE=%.6f" % initial_pa)
            self.gcode.run_script_from_command("_ERCF_ENDLESS_SPOOL_POST_LOAD")
            self.gcode.run_script_from_command("RESTORE_GCODE_STATE NAME=ERCF_PRE_UNLOAD")
            self.gcode.run_script_from_command("RESUME")

            self._enable_encoder_sensor()
        else:
            raise ErcfError("EndlessSpool mode is off - manual intervention is required")

    def _tool_to_gate(self, tool):
        return self.tool_to_gate_map[tool]

    def _tool_to_gate_map_to_human_string(self):
        msg = ""
        num_tools = len(self.selector_offsets)
        for i in range(num_tools):
            msg += "\n" if i else ""
            msg += "T%d -> Gate #%d" % (i, self._tool_to_gate(i))
            if self.enable_endless_spool:
                group = self.endless_spool_groups[i]
                es = ", EndlessSpool Grp %s: " % group
                prefix = ""
                for j in range(num_tools):
                    check = (j+ i + self.gate_selected) % num_tools
                    if self.endless_spool_groups[check] == group:
                        es += "%s%s%d" % (prefix, ("#" if self.gate_status[check] == self.GATE_AVAILABLE else "e"), check)
                        prefix = " > "
                msg += es
            if i == self.tool_selected:
                msg += " [SELECTED on gate #%d]" % self._tool_to_gate(i)
        msg += "\n"
        for i in range(len(self.gate_status)):
            msg += "\nGate #%d %s" % (i, "Available" if self.gate_status[i] == self.GATE_AVAILABLE else "Empty" if self.gate_status[i] == self.GATE_EMPTY else "Unknown")
            if i == self.gate_selected:
                msg += " [ACTIVE supporting tool T%d]" % self.tool_selected
        return msg

    def _remap_tool(self, tool, gate, available):
        self.tool_to_gate_map[tool] = gate
        self.gate_status[gate] = available

### GOCDE COMMMANDS FOR RUNOUT and GATE LOGIC ##################################

    cmd_ERCF_ENCODER_RUNOUT_help = "Encoder runout handler"
    def cmd_ERCF_ENCODER_RUNOUT(self, gcmd):
        try:
            self._handle_runout()
        except ErcfError as ee:
            self._pause(ee.message)

    cmd_ERCF_DISPLAY_TTG_MAP_help = "Display the current mapping of tools to ERCF gate positions. Used with endless spool"
    def cmd_ERCF_DISPLAY_TTG_MAP(self, gcmd):
        msg = self._tool_to_gate_map_to_human_string()
        self._log_always(msg)

    cmd_ERCF_REMAP_TTG_help = "Remap a tool to a specific gate and set gate availability"
    def cmd_ERCF_REMAP_TTG(self, gcmd):
        tool = gcmd.get_int('TOOL', minval=0, maxval=len(self.selector_offsets)-1)
        gate = gcmd.get_int('GATE', minval=0, maxval=len(self.selector_offsets)-1)
        available = gcmd.get_int('AVAILABLE', 1, minval=0, maxval=1)
        self._remap_tool(tool, gate, available)
        self._log_info(self._tool_to_gate_map_to_human_string())

    cmd_ERCF_RESET_TTG_MAP_help = "Reset the tool to gate map"
    def cmd_ERCF_RESET_TTG_MAP(self, gcmd):
        for i in range(len(self.selector_offsets)):
            self.tool_to_gate_map[i] = i
            self.gate_status[i] = self.GATE_AVAILABLE
        self._unselect_tool()
        self._log_info(self._tool_to_gate_map_to_human_string())

    cmd_ERCF_CHECK_GATES_help = "Inspects gates and marks availability"
    def cmd_ERCF_CHECK_GATES(self, gcmd):
        if self._check_not_homed(): return
        gate = gcmd.get_int('GATE', -1, minval=0, maxval=len(self.selector_offsets)-1)
        if gate == -1:
            gates = range(0, len(self.selector_offsets))
        else:
            gates = [gate]

        self._unselect_tool()
        for i in range(len(gates)):
            self._select_gate(gates[i])
            self._counter.reset_counts()    # Encoder 0000
            try:
                self._load_encoder(retry=False)
                self._log_info("Gate #%d - filament detected. Marked available" % i)
                self.gate_status[i] = self.GATE_AVAILABLE
                try:
                    self._unload_encoder(self.unload_buffer)
                except ErcfError as ee:
                    self._servo_up()
                    self._log_always("Failure during gate check: %s" % ee.message)
                    return
            except ErcfError as ee:
                self._log_info("Gate #%d - filament not detected. Marked empty" % i)
                self.gate_status[i] = self.GATE_EMPTY
        self._select_tool(0)
        self._log_info(self._tool_to_gate_map_to_human_string())

    cmd_ERCF_PRELOAD_help = "Preloads filament at specified or current gate"
    def cmd_ERCF_PRELOAD(self, gcmd):
        if self._check_not_homed(): return
        if self._check_is_loaded(): return
        gate = gcmd.get_int('GATE', -1, minval=0, maxval=len(self.selector_offsets)-1)
        try:
            # If gate not specified assume current gate
            if gate == -1:
                gate = self.gate_selected
            else:
                self._select_gate(gate)
            self._counter.reset_counts()    # Encoder 0000
            for i in range(5):
                try:
                    encoder_moved = self._load_encoder(retry=False)
                    # Caught the filament, so now park it in the gate
                    self._unload_encoder(self.unload_buffer)
                    self.gate_status[gate] = self.GATE_AVAILABLE
                    return
                except ErcfError as ee:
                    # Exception just means filament is not loaded yet, so continue
                    self._log_debug("Exception on encoder load move: %s" % ee.message)
                    pass
            self.gate_status[gate] = self.GATE_EMPTY
            self._log_always("Filament not detected in gate #%d" % gate)
        except ErcfError as ee:
            self._log_always("Filament preload for gate #%d failed: %s" % (gate, ee.message))
        finally:
            self._servo_up()


def load_config(config):
    return Ercf(config)
