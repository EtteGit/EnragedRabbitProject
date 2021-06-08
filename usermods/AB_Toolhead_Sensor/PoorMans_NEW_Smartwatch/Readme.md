# The "Poor man's SmartWatch" - New clockwork version
A new version of the clockwork extruder has been released, and this is an attempt to "sensorize" it, using the microswitch+ball combo.
While still functional, the old releases (AboveAndBelowGears, OnlyAboveGears, OnlyBelowGears) are not recommended, due to the improved functionality that the new clockwork design gives.

## Main features
- Cheap, reliable and wear resistant toolhead sensor mechanism.
- Removed the screwed in M10 pneumatic fitting for a standard ECAS one (closer to ERCF BOM).
- Added a side M3 screw that allows tweaking of sensor sensitivity.
- Unified the desing to have just one sensor placed below the BMG gears.
- Improved printability of ball slot.

## BOM
- n°1 Standard microswitch from Voron BOM. The Omron D2F-5 is recommended for reliability.
- n°1 7mmm diameter steel ball from any source (Amazon boxes for decorative work are a fine source)
- n°1 M2x8 or M2x10 self tapping screw.
- n°1 M3x10 bolt (a longer one will do fine).
- n°1 heat set insert
- wiring and connectors of choice

## Streamlined instructions
- Print the two STLs (Extruder body and Reinforced Latch) from this repository and the other clockwork parts from original Voron STLs. 
- Add the heatset insert in the side slot (take a look at CAD if in doubt), and the ECAS fitting on top. Be gentle or you will crack the part.
- Insert the ball in the bottom slot, followed by the microswitch as shown in the image. Take care to solder wires *before* insertion. 
NO wiring is easier to fit.
![Assembly Example](Images/AssemblyExample.jpg)
- Secure the microswitch with M2 screw only on one side. Do not overtigthen the screw, the switch needs to be able to sligthly pivot around the screw. 
- Insert the M3 bolt from the side and tighten it until it gently pushes against the bottom of the switch. Insert a piece of filament in the filament path and use the bolt to "register" the microswitch positioning. This bolt will be accessible also when mounted on toolhead.
- Finish the clockwork assembly following the original manual, wire the switch to an available slot on the SKR and you're good to go.

## Notes
Kudos to *kageurufu* for his work on the ECAS fitting, and to *Alch3my* and *Th3FalleN* for the pivoting switch idea.
