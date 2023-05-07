
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

## Updates

-**20 MARCH 2023:** Initial beta release

-**7 MAY 2023:** Sturdy Bunny V2 dev update

# Details
## Sturdy Bunny V2

<img width="800" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658815-3631c019-a115-453e-a194-e565a0d9096a.jpg"> <img width="800" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658830-1aa56b70-eb8a-41bf-abbf-0f45786861f7.jpg">

The sturdy bunny V2 has been released in a "development" state. That means it is still actively being worked on. It has been released in this way to provide some insight into what is being developed, and what direction development is taking.

This is *not* a final release, and it will not see a final release. Instead, the scope has increased dramatically and involved many other members of the ERCF community. Therefore, sturdy bunny will be incorporated into a much more comprehensive update to the ERCF system as a whole. More information to come soon...

### Changelog

Changes will be summarised here, and explained in further in the proceding sections below.
- Major componenets are mounted on a 2020 extrusion, rather than threaded rods. This improved stiffness of the overall system significantly
- All parts are now supportless & pre-orientated
- Filament passthrough incorporated into filament endblock
- There is only one type of filament block, and each have a bearing. Bearing support inserts have been removed.
- A tool is included to help press the bearings into the filament blocks
- The gearbox housing has seen significant reinforcement, and removed the twisting moment caused by the overhang fasteners. This has prevents twisting of the gearbox when the fasteners are too tight.
- Top hat magnets have been offset, so they do not cover the fastener hole
- An optional one-piece integrated top hat has been added
- An optional cover for the EASY BRD has been added
- General detailing & design improvements
- The sturdy bunny is taller than the original ERCF to make room for cable routing, but maintains the same mounting positions

### Filament Block

| Left Side  | Right Side | Internal |
| ------------- | ------------- | ------------- |
| <img height="300" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658927-74f9ad1d-6617-4e38-b828-687260cee1d7.jpg"> | <img height="300" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658918-0db74c75-deb3-4077-96cd-41d59471f78e.jpg"> | <img height="300" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658936-2f5bdc00-88f3-45ed-b758-6668b1f7abe3.jpg"> |

The filament blocks have been modified to fit on a 2020 extrusion. The top hat magnets have been offset to avoid the mounting fasteners. The lever has been modified slightly to reduce the amount of support material required.

### Top Hat

<img height="400" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658933-a55ee58c-c851-4021-81c7-3d127e49d3dd.jpg">

An optional integrated-one piece top hat has been included. You can use the standard non-integrated version if you prefer as well.

### Gearbox


| Overall | Topside | Underside |
| ------------- | ------------- | ------------- |
| <img height="300" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658970-55874876-4133-495f-9a53-e3beb9f32471.jpg"> | <img height="300" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658976-0446c83d-a9cf-4c77-bdc3-38dac2fd263c.jpg"> | <img height="300" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658977-d4c65d5b-afc4-4246-b35b-633c29fb7e62.jpg"> |

The gearbox has been heavily reinforced. The long screws that are offset from their support have also been removed & replaced, as they tended to twist and warp the entire gearbox if done up too tight. Removing this resulted in a gearbox that is now always square, preventing excess friction on the bearings & bending of the D shaft.

### Passthrough

<img height="400" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236659029-c6a043c1-d405-4e2a-8b2e-6c249316620d.jpg">

A filament passthrough has been added to the filament end block (the hinge part).

### EASY BRD

<img height="400" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658896-dd862fa5-8eec-407b-81f2-5045a9beefe6.jpg">

A lower EASY BRD mount, with optional cover has been added. This allows cables to be routed underneath along the extrusion, and few directly into the PCB.

### Supports

| Filament Block  | Top Hat |
| ------------- | ------------- |
| <img height="300" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236659039-c9d44142-6d19-4de4-a45c-7d66946e8a6d.jpg"> | <img height="300" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236659044-3c4ff35a-cf3b-4b2b-99d7-bcb8212bb5de.jpg"> |

All parts are either supportless, or have been pre-supported.

### Other

<img width="600" alt="Screen Shot 2022-06-23 at 6 24 17 PM" src="https://user-images.githubusercontent.com/12782053/236658832-80d5d498-b89b-4692-86d3-f47371750ed4.jpg">

The lower gearbox part has cable routing grooves added. The mounting feet have also been made taller - but they have not changed position, so existing mount designs are still compatible.

## BOM

TBD!

However, it is essentially unchanged from the stock ERCF, except removing the threaded rods and replacing that with a 2020 extrusion.

## Project Status

### 20 March 2023:
Proof of concept is running and working on my own V2.4. I personally found it much easier to build and it required substantially less tuning. Only one set of top hat lockers were required (Top_Hat_Locker_1), and this was the same for all filament blocks. I also noticed the gear D-shaft was a lot more stable due to more rigid bearing mounts. 

Some beta testers would be greatly appreciated, which would allow this project to move to the next steps.

#### Intended upcoming changes

- ~~Integrate the top hat with the top hat lockers. There is no longer a need to have them seperate/adjustable tension.~~
- ~~With the changes made to some parts, they have become more difficult to print (aka require support). I intend to modify them so they no longer require supports.~~

### 7 May 2023

Working to integrate into a more comprehensive ERCF update with other community members...

Beta testers are always appreciated.
 
## Acknowledgements

- Thanks to the original designer, Ette, for developing the ERCF in the first place.
- @jmack89427, for beta testing and trying out different filament block support methods

