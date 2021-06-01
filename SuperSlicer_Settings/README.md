# SuperSlicer settings

I'm using SuperSlicer (https://github.com/supermerill/SuperSlicer) with my ERCF.

Here is a collaborative, open table to share [proper purging volumes](https://docs.google.com/spreadsheets/d/11onBwd85u0-9houRi6wMT2FBWrvbKk8fzwE3qLjkN1w/edit?usp=sharing). Please respect the table layout and don't delete//edit other people's inputs :) .

Here are my SuperSlicer settings related to the multimaterial :

## Printer Settings
#### Custom G-code
Tool change G-code : nothing (leave it empty)

#### Single extruder MM setup
Cooling tube position : 40mm
Cooling tube length : 20mm
Filament parking position : 85mm
Extra loading distance : -83mm
High extruder cyrrebt on filament swap : off

Important : those settings are tested for a Dragon Normal Flow hotend! If you have a different hotend, you'll have to tune those numbers.

## Filament Settings

Each filament (brand, type or even just color) behaves differently. The goal of tuning those filament settings is to end up, at every single filament change, with a nice filament tip.

What is a nice filament tip?? It's a tip withtout long hairs, without blobs, with a proper, well defined, diameter. It should more or less look like a nice spear end.

Filament tip tuning is THE MOST IMPORTANT setting in your MMU setup, period. So take the time to tune those, it's really worth it!
The default filament settings associated with the PrusaMMU2S profile in prusa//super slicer are a very good starting point!

Esun ABS+ : use default multimaterial settings from the MMU2S profile (PrusaABS filament profile), and add a skinnyDip string reduction sequence with 42mm insertion distance, 0ms of pause, 33mm/s speed to move into the melt zone and 70mm/s speed to extract from the melt zone
