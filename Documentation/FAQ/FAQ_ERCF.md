# Enraged Rabbit Carrot Feeder (ERCF) F.A.Q.

Here is the FAQ for the Enraged Rabbit Carrot Feeder.

**Q: My encoder (TCRT5000) is always on/red, what is going on ?**  
**A:** Remove the TCRT5000 from the encoder cart and check that:
	- It is off when there is nothing in front of the sensor
	- It turns on / red when you bring something reflective in front of it, like
	a metallic tool

If the sensor is always on / red even if there is nothing in front of it, it is 
probably dead (either DOA or you miss-plugged the 5V into the signal for example).

If it behaves as expected from this test, check the distance between the TCRT5000 
sensor and the BMG gear of the encoder cart. The black plastic wall between the two IR Leds of the sensor
have to be very close to the BMG dual gear part, but not touching it. If it is 
too far, gently file down the 3D printed part where the TCRT5000 rests (i.e. where it is screwed) too get it closer to the gear.

In case you printed the encoder cart with bright filament (e.g. white or yellow) it may be possible that the plastic cart itself is too reflective, making the sensor being always on/red. If so, try printing the encoder cart using a black filament.

**Q: When performing the test grip, using higher Top Hat Lockers makes the servo arm go back after the "ERCF_SERVO_DOWN" move, lowering the grip on the filament.**  
**A:** Increase a bit the servo_down angle so it pushes further.

**Q: While everything is working fine on TX commands out of a print, during a print the servo will engage and then directly disengage before the unload move.**  
**A:** This is a Klipper issue with servos and timing. If this happens to you, change one of the "G4 P100" of the ERCF_SERVO_DOWN macro (ercf_software.cfg) into a "G4 P105". This will add 5ms of dwell for this sequence and fix your issue. Note that this issue cannot be predicted, as it is related to the hardware (mcu, servos) you are using.

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