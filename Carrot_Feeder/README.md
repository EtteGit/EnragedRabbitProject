# Study Bunny Assembly Notes

## Sturdy Bunny V1

This section will focus on the major changes to the base ERCF components. Further changes can be found here.

The gearbox, hinge and filament blocks now mount directly onto a 2020 extrusion. This greatly improves the overall accuracy and robustness of the assembly.

<img width="800" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/226225720-cfacdb08-269f-4be1-810b-a93ab9154093.png">

Filament support blocks have been removed and replaced with filament blocks with an integrated bearing.

<img height="400" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/226225330-064feb2d-c447-4527-8a9c-337875b22342.png"> <img height="400" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/226225318-3eb1578d-2ed4-42f6-931a-641c32d659ee.png">

## Assembly

The installation is generally the same as the standard ERCF - refer to the manual there. Proper instructions will come soon...

### 2020 Extrusion Length

The 2020 extrusion length is calculated by:

extrusion length [mm] = 45 + 21 * filament_blocks + 26 * filament_blocks_bearing

The length doesn't have to be perfect, there is some "wiggle room".

## What to print

### Filament Blocks

- **"FILAMENT_BLOCK_BEARING_V1A.stl"** QTY = floor((n+1)/3) = b. (For n = 9, QTY = 3)
- **"FILAMENT_BLOCK_V1A.stl"** QTY = n - b. (For n = 9, QTY = 6)

Where n is the number of ERCF filament tracks.

You should only need to print the "Top_Hat_Locker_1_xN.stl". Please contact me and let me know if this is not the case, and you have to use the higher pressure top hat lockers.

### Supports

This mod uses the same mounting interface as the standard ERCF, so existing ERCF mounting/support solutions will remain compatible.

### EASY BRD

A modified bracket for the EASY BRD has been included in the STL folder of this project, called "[a]ERCF_EASY_BRD_BRACKET_V1A.stl"

### Other

For ease of cable management, I recommend attaching some cable management clips to the 2020 extrusion. I use [this design](https://www.printables.com/model/6593-2020-extrusion-zip-tie-clip).

