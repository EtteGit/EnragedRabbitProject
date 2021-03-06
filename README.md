# EnragedRabbitProject

Welcome to the Enraged Rabbit Project Github page!

This project aims to bring multimaterial capabilities to 3D printers using a single Direct Drive toolhead, similar to what the Prusa MMU2 does. While this project is mainly dedicated to be used on Voron V2s, the main components can also be used on any 3D printer that runs Klipper.

 You like this project? You want to support me and my work, help me bring new cool stuff to the community? Well you can tip me here :
[![paypal](https://www.paypalobjects.com/en_US/FR/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate?business=C9MG5LQSQRKN4&currency_code=EUR)

### Showroom : 

<img src="https://cdn.discordapp.com/attachments/603294954382426133/811963167168266270/20210218_150835.jpg" alt="Carrot Feeder" width="340"/><img src="https://cdn.discordapp.com/attachments/603294954382426133/812222776512348200/20210219_081627.jpg" alt="Carrot Feeder" width="600"/>

### Videos of the system in action :
https://streamable.com/3lo192

https://streamable.com/cjl2iz

### Details :

There are 4 components so far : 
 - **The Carrot Feeder** : this is the main unit. The Carrot Feeder allows to use a high number of different filaments (tested up to 9 channels so far) and feed them, one at a time, into the printer toolhead. The Carrot Feeder gear motion system (i.e. what is used to push and pull the filament) uses part of the Voron Design M4 extruder (namely the whole 80T wheel and part of the motor support//tensionning system).
 
  <img src="https://cdn.discordapp.com/attachments/500407802414628876/805813965933772850/20210201_155417.jpg" alt="Carrot Feeder" width="600"/><img src="https://cdn.discordapp.com/attachments/500407802414628876/805813967435595776/20210201_155457.jpg" alt="Carrot Feeder 2" width="600"/>
 
 - **The Carrot Patch** : a spool-holder and buffer combo to help you deal with the filament management issue associated with multimaterial systems.
 
 <img src="https://cdn.discordapp.com/attachments/788818216260337664/807282522756350022/image0.jpg" alt="Carrot Patch" width="300"/><img src="https://cdn.discordapp.com/attachments/500407802414628876/806108474668613632/20210202_112459.jpg" alt="Carrot Patch 2" width="300"/>
 - **The King's Seat** : a pellet-purge system to remove the need for a wipe-tower and make faster filament purges. This system is designed for Voron V2s only so far.
 - **The filament sensor** : a filament sensor system located below the bondtech gears of the Voron V2 toolhead, to check proper loading//unloading of filament. So far only the Galileo version is available.
 
 You'll find more informations about each of those components into their respective folders. Note that this is a work in progress !!
 
 Only the King's Seat is yet to be released !
 
 The BOM for those components can be found here : https://docs.google.com/spreadsheets/d/1djVxoKnByb41ifVy2JTfhXmdf9UYpnUYfhvcNyUDuLw/edit?usp=sharing.
 
# FAQ
## General
**Q:** In what material should this be printed with?  
**A:** The whole design assumes it's printed in ABS, so printing it in PLA or PETG may result in poor fits//tolerances. 


**Q:** Can I use this system on another printer than a Voron V2?  
**A:** Yep, as long as your printer is running Klipper you should be good to go. Of course if you are not running an AfterBurner or Galileo Clockwork toolhead, you'll need to deisng your own filament sensor below your direct drive gears.


**Q:** Can I use a dedicated control board?  
**A:** Of course, klipper allows you to use as many MCUs as you want. In the end you'll need to control 2 stepper motors, 1 5V servo, 1 mechanical switch, 1 optical sensor and 1 filament detector.


## Carrof Feeder
**Q:** How many channels can I build on the Carrot Feeder?  
**A:** Only mechanical limitation will come from the length of the 5mm D-cut shaft that holds the Bondtech-type Gears. A 9 channel system will work (this is my own testing unit). Going higher (like 12 or 15) might be possible, but it hasn't been tested yet.


**Q:** Is there a cutter blade on the Carrot Feeder?  
**A:** Not yet, but this is planned


Thanks !!

Ette
