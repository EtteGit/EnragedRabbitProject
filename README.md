# EnragedRabbitProject

Welcome to the Enraged Rabbit Project Github page!

This project aims to bring multimaterial capabilities to 3D printers using a single Direct Drive toolhead, similar to what the Prusa MMU2 does. While this project is mainly dedicated to be used on Voron V2s, the main components can also be used on any 3D printer that runs Klipper. It was inspired by the Prusa MMU2 and the Smuff.

 You like this project? You want to support me and my work, help me bring new cool stuff to the community? Well you can tip me here :
[![paypal](https://www.paypalobjects.com/en_US/FR/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate?business=C9MG5LQSQRKN4&currency_code=EUR)

## Table of Content
- [Changelog](#changelog)
- [Showroom](#showroom)
- [Videos](#videos)
- [Details](#details)
- [BOM](#bom)
- [Acknowledgements](#acknowledgements)
- [FAQ](#faq)
  - [General](#general)
  - [Carrot Feeder](#carrot-feeder)
 
## Changelog
- June 2nd 2021 : Release of Carrot Patch V1.1
   - Increased handles section near the threaded insert for more robustness
   - Removed useless chamfer on feet bottom screw holes and increased hole depth (one can now properly use M3X8 SHCS to secure the Carrot Patch on 2020 extrusions)
   - Fixed several parts lengths//size that impacted the buffer wheel installation. Now the wheel should slightly touch both side walls (to avoid any possible gaps) while being able to turn (but not freely, which is on purpose)
   - Buffer Cross bottom arm is now secured using a M3X20 SHCS screw that comes from the bottom (that is also securing the left feet of the Carrot Patch)
   - Buffer Cross ECAS insert has been tuned, reinforced and a "bridge" shape has been added. Inserting the ECAS will no longer crack the plastic
   - Increased the size of the Buffer Cross "pillar" that sits between the two PTFE paths (some users previously reported fragilities due to the lack of matter for this pillar)
   - Updated the assembly manual, BOM and the CAD accordingly
   - Only parts that did not change are : [a]_Buffer_Wheel, [a]_Latch, [a]_Sliding_Arm, Buffer_Axis, Ptfe_Entry_ECAS and Ptfe_Entry_M10

## Showroom

<img src="Showroom/Benders.png" alt="Benders" width="950"/><img src=Showroom/Bimaterial_logo.png alt="Voron Logo TPU" width="650"/><img src=Showroom/5_colors_test.png alt="5_colors_test" width="300"/><img src=Showroom/9_colors_test.png alt="9_colors_test" width="400"/><img src="Showroom/Gustav_brothers.png" alt="Gustav brothers" width="550"/>

## Videos
Here are videos of the system in action. More will come.
https://streamable.com/3lo192

https://streamable.com/cjl2iz

## Details

There are 4 components so far : 
 - **The Carrot Feeder** : this is the main unit. The Carrot Feeder allows to use a high number of different filaments (tested up to 9 channels so far) and feed them, one at a time, into the printer toolhead. The Carrot Feeder gear motion system (i.e. what is used to push and pull the filament) uses part of the Voron Design M4 extruder (namely the whole 80T wheel and part of the motor support//tensionning system).
 
  <img src="https://cdn.discordapp.com/attachments/500407802414628876/805813965933772850/20210201_155417.jpg" alt="Carrot Feeder" width="600"/><img src="https://cdn.discordapp.com/attachments/500407802414628876/805813967435595776/20210201_155457.jpg" alt="Carrot Feeder 2" width="600"/>
 
 - **The Carrot Patch** : a spool-holder and buffer combo to help you deal with the filament management issue associated with multimaterial systems.
 
 <img src="https://cdn.discordapp.com/attachments/788818216260337664/807282522756350022/image0.jpg" alt="Carrot Patch" width="300"/><img src="https://cdn.discordapp.com/attachments/500407802414628876/806108474668613632/20210202_112459.jpg" alt="Carrot Patch 2" width="300"/>
 - **The King's Seat** : a pellet-purge system to remove the need for a wipe-tower and make faster filament purges. This system is designed for Voron V2s only so far.
 - **The filament sensor** : a filament sensor system located below the bondtech gears of the Voron V2 toolhead, to check proper loading//unloading of filament. There are versions available for :
   - Regular AfterBurner (AB) toolhead
   - Galileo Clockwork toolhead
   - LGX on AfterBurner (AB) toolhead
You'll find those either on the main project folder or in the usermods folders.
  
 You'll find more informations about each of those components into their respective folders. Note that this is a work in progress !!
 
 Only the King's Seat is yet to be released !
 
## BOM
 The BOM for those components can be found [here](https://docs.google.com/spreadsheets/d/1djVxoKnByb41ifVy2JTfhXmdf9UYpnUYfhvcNyUDuLw/edit?usp=sharing).
 
## Acknowledgements

Thanks to the Voron design devs and Voron discord members for the discussions and support, with a special thanks to the #honhonhonbaguette-FR members, especially @Tircown#8715!!
 
## FAQ
### General
**Q:** In what material should this be printed with?  
**A:** The whole design assumes it's printed in ABS, so printing it in PLA or PETG may result in poor fits//tolerances.


**Q:** What materials can be printed with the Enraged Rabbit?  
**A:** So far, PLA, PETG, ABS and TPU were all tested with success. For TPU, both 95A and 30D (~80A) were tested and could be loaded//unloaded using the Enraged Rabbit Carrot Feeder. While the 95A TPU was also working well with the Carrot Patch spool holder + buffer combo, the 30D TPU is way too soft to make filament "loops". If you plan to use such ultra-soft TPU, make sure the concerned Carrot Patch is located in a "clean" area (to avoid your TPU buffer length to be caught on something) or use another buffer//spool holder.


**Q:** Can I use this system on another printer than a Voron V2?  
**A:** Yep, as long as your printer is running Klipper you should be good to go. Of course if you are not running an AfterBurner or Galileo Clockwork toolhead, you'll need to deisng your own filament sensor below your direct drive gears.


**Q:** Can I use a dedicated control board?  
**A:** Of course, klipper allows you to use as many MCUs as you want. In the end you'll need to control 2 stepper motors, 1 5V servo, 1 mechanical switch, 1 optical sensor and 1 filament detector. A dedicated PCB will be designed, at some point (no ETA at all).


### Carrot Feeder
**Q:** How many channels can I build on the Carrot Feeder?  
**A:** Only mechanical limitation will come from the length of the 5mm D-cut shaft that holds the Bondtech-type Gears. A 9 channels system will work (this is my own testing unit). Going higher (like 12 or 15) is most likely possible, but it hasn't been tested yet.


**Q:** Is there a cutter blade on the Carrot Feeder?  
**A:** No, and it's not on the schedule (anymore). It seems to be, so far, not a needed feature.


Thanks !!

Ette
