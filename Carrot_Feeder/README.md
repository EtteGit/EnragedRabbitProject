# Study Bunny Assembly Notes

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

