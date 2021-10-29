# Enraged Rabbit Project F.A.Q.

Here is the FAQ for the Enraged Rabbit Project.
Check the .md files for each sub part of the project.

### General
**Q:** In what material should this be printed with?  
**A:** The whole design assumes it's printed in ABS, so printing it in PLA or PETG may result in poor fits or tolerances.


**Q:** What materials can be printed with the Enraged Rabbit?  
**A:** So far, PLA, PETG, ABS and TPU were all tested with success. For TPU, both 95A and 30D (~80A) were tested and could be loaded//unloaded using the Enraged Rabbit Carrot Feeder. While the 95A TPU was also working well with the Carrot Patch spool holder + buffer combo, the 30D TPU is way too soft to make filament "loops". If you plan to use such ultra-soft TPU, make sure the concerned Carrot Patch is located in a "clean" area (to avoid your TPU buffer length to be caught on something) or use another buffer//spool holder.


**Q:** Can I use this system on another printer than a VORON V2?  
**A:** Yep, as long as your printer is running Klipper you should be good to go. Make sure the toolhead you are using have a filament sensor below the extruder gear (VORON AfterBurner, Galileo and LGX on AfterBurner are officialy supported, but plenty other toolheads have been modified to fit such a sensor, look in the usermods folder of this repo).


**Q:** Can I use a dedicated control board?  
**A:** Of course, Klipper allows you to use as many MCUs as you want. In the end you'll need to control 2 stepper motors, 1 5V servo, 1 mechanical switch, 1 IR sensor and 1 filament detector. You can find a dedicated PCB, made by @Tircown, here : https://github.com/Tircown/ERCF-easy-brd.
