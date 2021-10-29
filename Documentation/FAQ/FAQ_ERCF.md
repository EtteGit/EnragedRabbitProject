# Enraged Rabbit Carrot Feeder (ERCF) F.A.Q.

Here is the FAQ for the Enraged Rabbit Carrot Feeder.

### Encoder
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

### Top Hats Lockers
**Q: When performing the test grip, using higher Top Hat Lockers makes the servo arm go back after the "ERCF_SERVO_DOWN" move, lowering the grip on the filament.**  
**A:** Increase a bit the servo_down angle so it pushes further.
