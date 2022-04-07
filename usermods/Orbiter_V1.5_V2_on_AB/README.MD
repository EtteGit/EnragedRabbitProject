Here are some cobbled up ERCF tool head sensors:

- inductive filament sensor/adapter for mounting the Orbiter v1.5 (and v2?) on the AB.
- mechanical filament sensor/adapter for mounting the Orbiter v1.5 on the AB.

The Orbiter V2 inductive sensor adapter is a remake of the same thing on the Orbiter 1.5 I originally did for myself.

I've tested and was using the inductive Orbiter 1.5 on V2.2526.  However, due to suspected thermal sensitivity (while it worked 100% outside of the printer), once installed and heated, reliability dropped substantively.  As such, I have since migrated to a bearing/microswitch setup and have had zero reliability issues since then.  Mechanical is the way to go here, I perceive.

The inductive Orbiter 2 is an alpha/beta/POC until it is tested and proven to work.  One user mentioned slight variances of the two main mount holes, but never got back with required geometry changes.

Print in the orientation depicted in the project files - no supports needed.  I used ABS with a typical Voron profile (240/120 temps, 0.4 noz, 0.2 LH, 4 walls, 5 top/bot layers, 40% infill, ...).

## For the inductive flavor:

Inductive BOM needs:  1ea/2ea 6x3 magnets, one of the iron washers used in the gates, the hall effect sensor in the ERCF kit, 6ea M3 heat inserts, a M3x8, the printed extruder adapter parts (2 pcs total), and 2 short bits of bowden tube:

- one 8.25mm piece from the Extruder into the throat of the adapter 
    - https://i.imgur.com/SoOvUEF.jpeg
- one 20.25mm(?) piece between the adapter into the throat of the hot end
    - https://i.imgur.com/e6WDewI.jpeg

NOTE:  Before I switched to the mechanical switch, I planned to double check these measurements when next I had the extruder removed from the tool head, but that never happened.  These tube measurements are relevant in the context of an Orbiter v1.5 on the attached adapter and a traditional AB install of a Dragon HF HE.  If you are using a different HE, then start out with a longer lower tube length and trim down in an iterative manner to arrive at a snug fit.  If one is using the Orbiter v2, then follow a similar process to arrive at the correct length of the upper tube.  In any case, if you are able to advise, I'll add those lengths herein for different HEs or for the Orbiter v2, to help peeps wishing to make use of same.

ERCF assy manual page 80/81 are applicable as it relates to the innards.

I added a JST 2.0 3-pin connector after I hobbed out some material to make room for it (post processing ya know...), but one could just run wires to an inline disconnect at the tool head or similar.

https://cdn.discordapp.com/attachments/928716501480009768/938473912537350194/2022-02-02-11-36-55.png

ERCF Manual shows only 1 magnet.  I ended up needing to stack 2 (the top one is a bit proud but space isn't an issue on the 1.5 mounted to an AB carriage with this adapter).  https://i.imgur.com/W8hy9hX.png

There's some dialog about the sensor being pole sensitive, so maybe that is why I had to use two.?.  w/e - it works...  

https://cdn.discordapp.com/attachments/928716501480009768/938505236845330472/20220202_134303.mp4

EDIT:  Besides the sensitivity of the hall effect sensor wrt N/S poles of the magnets,  there are different magnet types and numerous types of hall effect sensors.  The hall effect sensor model that is in the kit has been vetted by Ette for stability and use as the tool head filament detector in the hot environment of an enclosed Voron print volume (it's rated to 150 C).  Also, note that these hall effect sensors are open drain devices - presenting a hi-z open when there is no filament detected and connected to ground when filament is detected.  This means that the signal input to the MCU should have the internal pull-up enabled (^) and have inverted logic enabled on said input (!):  https://i.imgur.com/XfR8kqq.png 

## For the mechanical flavor:

A .stl is provided.  If one desires to see how I did this in PS from a blank adapter, I have also provided a .3mf project file.  The .3mf needs to be opened and sliced in Prusa Slicer >=v2.4.1, as it makes use of Negative Space Modifiers to redact material from a blank adapter model for the bearing cavity, the microswitch/attaching screws, the JST 2.0mm 3-pin male header, and the wire path from the switch to the JST (I used 30awg silicone insulated (wirewrap) wires for same.  I slice the model and saved the gcode.  I then used Voxelizer to take the gcode and create a .stl from the sliced gcode.  The back way around, admittedly, but it works and helps me to avoid learning 3D CAD that much longer... ;)

BOM:

- 1ea printed adapter set (both front and back models)
- an Omron D2F-01 or similar (typical endstop switches)
- 2ea self-tapping M2.5 x 10mm screws
- 1ea 4mm (or 4.5mm*) Bearing
- 1ea JST 2.0 3-pin connector pair (male on the adapter, female on wire side)
- ~6" of 30AWG silicone insulated (or similar) wire

*The bearing cavity/throat was originally designed for a 4.5mm bearing, as I thought I had them on hand but nope, so I made use of a 4mm bearing and have experienced no issues.  It just works.  It's so much better than fighting with lines of flux... ;)

## Happy Printing!

Enjoy.

~MHz

(P.S.  Don't judge.  lol.  These were cobbled together from several models using Prusa Slicer as a CAD alternative.  I have absolutely zero/naught/nil 3D CAD skills, so this is the best I am capable of ATM. 🙂 )
