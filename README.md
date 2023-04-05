
# SturdyBunnyProject

Welcome to the Sturdy Rabbit Project Github page!

This project builds upon the Enraged Rabbit Project, which aimed to bring multimaterial capabilities to 3D printers using a single Direct Drive toolhead. In this project, an effort has been made to improve the repeability, robustness and reliability of the ERCF.

<img width="800" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/226226559-092b9676-5ea6-4a88-99c5-af5e44d0df45.jpeg">

## Table of Content
- [Changelog](#changelog)
- [Details](#details)
- [BOM](#bom)
- [Acknowledgements](#acknowledgements)
 

## Motivation

Although the core concept of the ERCF design is great and can work very well, I found it very difficult to get it working reliably. I believe this is in part due to the overall stiffness and rigidity of the ERCF filament blocks, especially when there are a lot of them (>6).

In my experience, I found that:
- There is quite a lot of flexibility in the filament blocks. When the filament lever presses on the filament locker, it causes flex along the entire assembly. The amount of flex is different for each filament block, so different tolerance locker hats are required to account for this.
- The lack of rigidity in the frame can result in damage if you are not careful. I had put a slight bend in the gear D-shaft while lifting the assembly from one end.
- The lack of rigidity in the frame seems to imply that a robust mounting solution is required instead.
- Using threaded rods to hold all the filament blocks together is someone user prone. Overtightening can cause parts to fail, and undertighhtening leads to a sloppy and loose assembly. Furthermore, it is impossible to remove only one filament block from the assembly at the time.

In general, this made for an assembly that took quite a long time to tune to get right, and even then it was not particularly reliable and would often have issues.

### Goal

For the reasons stated above, I believe that a few modifications can be made to vastly improve the robustness, ease of assembly/tuning and reliability of the ERCF design. 
My goals with this project can be summarised below:

- maintain the original design intent with how the ERCF is supposed to function. The overall concept of the ERCF is great and I am yet to see a reason to change that.
- Improve the robustness by making the ERCF assembly self-supporting, so that it does not require an external frame/mount for rigidty.
- Reduce the opportunity for user error during assembly, and by consequence, reduce the amount of tuning required to make of for variations in the assembly.
- Improve repeatability of the system during filament loading/unloading.

I do not intend to modify the filament carriage in this project.

## Changelog

-**20 MARCH 2023:** Initial beta release

## Details

This section will focus on the major changes to the base ERCF components. Further changes can be found here.

The gearbox, hinge and filament blocks now mount directly onto a 2020 extrusion. This greatly improves the overall accuracy and robustness of the assembly.

<img width="800" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/226225720-cfacdb08-269f-4be1-810b-a93ab9154093.png">

Filament support blocks have been removed and replaced with filament blocks with an integrated bearing.

<img height="400" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/226225330-064feb2d-c447-4527-8a9c-337875b22342.png"> <img height="400" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/226225318-3eb1578d-2ed4-42f6-931a-641c32d659ee.png">
 
## BOM

TBD!

However, it is essentially unchanged from the stock ERCF, except removing the threaded rods and replacing that with a 2020 extrusion.

## Project Status

Proof of concept is running and working on my own V2.4. I personally found it much easier to build and it required substantially less tuning. Only one set of top hat lockers were required (Top_Hat_Locker_1), and this was the same for all filament blocks. I also noticed the gear D-shaft was a lot more stable due to more rigid bearing mounts. 

Some beta testers would be greatly appreciated, which would allow this project to move to the next steps.

### Intended upcoming changes

- Integrate the top hat with the top hat lockers. There is no longer a need to have them seperate/adjustable tension.
- With the changes made to some parts, they have become more difficult to print (aka require support). I intend to modify them so they no longer require supports.
 
## Acknowledgements

- Thanks to the original designer, Ette, for developing the ERCF in the first place.
- @jmack89427, for beta testing and trying out different filament block support methods

