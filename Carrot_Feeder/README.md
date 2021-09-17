# ERCF V1.1 Patch Note (non exhaustive)
This is a major update. If you already have a, ERCF V1.0, please reprint all the parts for V1.1. Feet anchoring points are unchanged.

## Hardware:
### Filament Blocks:
- Updated filament path to limit unselected filament being pulled or pushed by the rotating gear. The grip on the filament is also drastically improved
- Fixed the ECAS insert slot
- Removed the threaded insert version as the direct plastic tapping was sufficient
- New and improved number tag plate (easy to install and remove, much more robust than before)
- Added magnetic gates at the exit of each filament block : using a M3 Steel washer and magnets, the filament path of each filament block will be closed at the filament block exit when the selector is not in front of it, ensuring that no unselected filament can stick out and block the selector cart during a tool change
### Top Hats :
- Redesign of the Top Hat arm to avoid it's ejection when opening the filament block latch
- Top Hat Lockers are now easier to print (more contact area with the print surface)
- New slide-in mechanism for the Top Hat Lockers
- Top Hat Locker will no longer touch the Filament Block Latch, which is no only touching the Top Hat
- BMG gear can no longer be installed in the wrong orientation in the Top Hat
- Moved the servo pressure point on the Top Arm Locker to have a better grip on filament
### Gear Box :
- Gear motor is now a low rotor inertia NEMA 14, allowing a smaller footprint, quieter operation and faster loads and unloads (NEMA 17 motors are still 100% compatible)
- Added a bearing on the Gear Box Back to better constrain the 5mm D-Cut shaft and remove potential longitudinal play
- Motor Arm infamous overhang is now easy to print
- Added a customisable, multicolor logo on the front, which is easy to change
- Minor fixes (micro switch lever colliding with 3D printed part, more plastic matter behind the left side latch threaded inserts...)
### Bearing Blocks :
- Added foot to improve global stiffness, especially for long units. It can be install and removed easily without dismounting the unit
### Selector Motor Support :
- Fixed the 8mm rod hole issue (same for the Idler Block)
- Fixed the selector motor screws issue
### Selector Cart :
- Old filament sensor is gone. Now there is an amazing encoder, idea and design by @Tircown! Encoder fits in the ERCF selector cart, has a 1.3mm resolution and can keep up with very fast movement (20cm/s +). Allows to precisely track filament load and unload, potential clogs during a print and is also used as filament runout sensor
- New servo ref. Easier to source, quieter and much cheaper than V1.0 model, works well with the new Top Hat Locker and - Filament Blocks design. V1.0 servo model is still 100% compatible
- Mystery stuff hidden behind the new selector cart door, can you guess what it is from the charade hidden in the ERCF?

## Software:
To use the new selector encoder, part of the software have to be done in the python part of Klipper. The ERCF V1.1 software will now include a .py file and the usual cfg files. The GCODE macros are still in use, but are much smaller.

Regular update and improvements will be done on the software side, as using the python part of Klipper allows for much more complex and fancy stuff to be done.