Here is a cobbled up ERCF tool head filament sensor/adapter for mounting the Orbiter 2 on the AB.  This is a remake of the same thing on the Orbiter 1.5 I did for myself.  That too is attached hereto.

I've tested and am using the Orbiter 1.5 on V2.2526.  The Orbiter 2 is an alpha/beta/POC until it is tested and proven to work.

BOM needs:  1ea/2ea 6x3 magnets, one of the iron washers used in the gates, the hall effect sensor in the ERCF kit, 6ea M3 heat inserts, a M3x8, the printed extruder adapter parts (2 pcs total), and 2 short bits of bowden tube:

- one 8.25mm piece from the Extruder into the throat of the adapter 
    - https://i.imgur.com/SoOvUEF.jpeg
- one 20.25mm(?) piece between the adapter into the throat of the hot end
    - https://i.imgur.com/e6WDewI.jpeg

NOTE:  I'll double check these measurements when next I have the extruder removed from the tool head.  These tube measurements are relevant in the context of an Orbiter v1.5 on the attached adapter and a traditional AB install of a Dragon HF HE.  If you are using a different HE, then start out with a longer lower tube length and trim down in an iterative manner to arrive at a snug fit.  If one is using the Orbiter v2, then follow a similar process to arrive at the correct length of the upper tube.  In any case, if you are able to advise, I'll add those lengths herein for different HEs or for the Orbiter v2, to help peeps wishing to make use of same.

Print in the orientation depicted in the project files - no supports needed.  I used ABS with a typical Voron profile (240/120 temps, 0.4 noz, 0.2 LH, 4 walls, 5 top/bot layers, 40% infill, ...).

ERCF assy manual page 80/81 are applicable as it relates to the innards.

I added a JST 2.0 3-pin connector after I hobbed out some material to make room for it (post processing ya know...), but one could just run wires to an inline disconnect at the tool head or similar.

https://cdn.discordapp.com/attachments/928716501480009768/938473912537350194/2022-02-02-11-36-55.png

ERCF Manual shows only 1 magnet.  I ended up needing to stack 2 (the top one is a bit proud but space isn't an issue on the 1.5 mounted to an AB carriage with this adapter).  https://i.imgur.com/W8hy9hX.png

There's some dialog about the sensor being pole sensitive, so maybe that is why I had to use two.?.  w/e - it works...  Enjoy.  Happy Printing.

https://cdn.discordapp.com/attachments/928716501480009768/938505236845330472/20220202_134303.mp4

(P.S.  Don't judge.  lol.  This was cobbled together from several models using Prusa Slicer as a CAD alternative.  I have absolutely zero/naught/nil 3D CAD skills, so this is the best I am capable of ATM. 🙂 )

EDIT:  Besides the sensitivity of the hall effect sensor wrt N/S poles of the magnets,  there are different magnet types and numerous types of hall effect sensors.  The hall effect sensor model that is in the kit has been vetted by Ette for stability and use as the tool head filament detector in the hot environment of an enclosed Voron print volume (it's rated to 150 C).  Also, note that these hall effect sensors are open drain devices - presenting a hi-z open when there is no filament detected and connected to ground when filament is detected.  This means that the signal input to the MCU should have the internal pull-up enabled (^) and have inverted logic enabled on said input (!):  https://i.imgur.com/XfR8kqq.png 
