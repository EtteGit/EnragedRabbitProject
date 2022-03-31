# Enraged Rabbit Carrot Feeder (ERCF) F.A.Q.

Here is the FAQ for the Enraged Rabbit Carrot Feeder.

**Q: My encoder (TCRT5000) is always on/red, what is going on ?**  
**A:** Remove the TCRT5000 from the encoder cart and check that:
	- It is off when there is nothing in front of the sensor
	- It turns on / red when you bring something reflective in front of it, like
	a metallic tool

If the sensor is always on / red even if there is nothing in front of it, it is 
probably dead (either DOA or you miss-plugged the 5V into the signal for example).

Make sur you did print the encoder_cage in a black filament, to avoid IR reflections.

Don't forget to use the M3x16 SHCS bottom screw of the encoder cart to adjust the sensor height relative to the BMG gears.
You can also use a M3x8 SHCS on the hole below the bearing "spring" to increase the spring tension on the ilder, in case you need to.

**Q: When performing the test grip, using higher Top Hat Lockers makes the servo arm go back after the "_ERCF_SERVO_DOWN" move, lowering the grip on the filament.**  
**A:** Increase a bit the servo_down angle so it pushes further.

**Q: While everything is working fine on TX commands out of a print, during a print the servo will engage and then directly disengage before the unload move.**  
**A:** This is a Klipper issue with servos and timing. If this happens to you, adjust a bit the variable_extra_servo_dwell_down value in the ercf_software.cfg, this will add some ms of dwell for this sequence and fix your issue. Don't forget to reload the firmware for it to work. Try increments of 2, but remember that maybe you'll need 2, 5 or even. Note that this issue cannot be predicted, as it is related to the hardware (mcu, servos) you are using.

**Q: My printer issued a "Move out of range" error after the resume following and ERCF_PAUSE.**  
**A:** Make sure you are using the proper PAUSE and RESUME macros from the Enraged Rabbit GitHub repository (in the client_macros.cfg) and that no other similar macros are in your Klipper config files. What is happening here is that other PAUSE and RESUME macros are being used, and the printer restarts the print in the relative positioning mode, resulting in moves that are out of the print area.

**Q: Sometimes the gear motor is making a very loud and high pitch noise.**  
**A:** This means the motor is skipping. Make sure there are no mechanical constraints on the 5mm D-Cut shaft. For instance, make sure that the tension on the 188GT belt is not too high (there is no need for high tension on the ERCF) and that the two 5mm threaded rods are not overtighten, as this will cause the whole ERCF to bend.
Also make sure that the configuration is matching your motor properties (current, accel, speed, stealthchop threshold etc.)

**Q: What are the 2020 extrusion length for the V1/V2 support.**  
**A:** They are the same as the horizontal profiles on your printer. For instance on a V2 300 those are 420 mm long.

**Q: The toolhead hall effect sensor is not working**  
**A:** First, make sure you are using the proper hall effect sensor (i.e. AH3364, nothing else).
Second, beware that low-strength magnets will not work properly. Try to get a N51 or N52 grade magnet.
Third, you need proper M3 DIN125 ferromagnetic washers. This means you need Steel (galvanized or zinc-plated for example), not Stainless Steel. Also make sure the washer is free of any bur, otherwise it can be stuck in its groove.

If you still have issues, make sure that the hall effect sensor is properly installed in its slots and firmly secured (using the dedicated screw) and remember to test both magnet polarities.our motor properties (current, accel, speed, stealthchop threshold etc.)