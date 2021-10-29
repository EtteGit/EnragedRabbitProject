# Enraged Rabbit Carrot Patch (ERCP) F.A.Q.

Here is the FAQ for the Enraged Rabbit Carrot Patch.

### General
**Q: How does this work?**  
**A:** The spool holding part is a direct copy of the nominal spool holder on Vorons, i.e. an arm with a 4mm PTFE tube on which the spool rests and turns around. The buffer part of the Carrot Patch, which is inspired from several similar open-source designs, consists of a big wheel located in a filament "cage". Filament from the spool enters the filament cage, makes a few turns around the wheel and then exit the cage through a PTFE tube. When the extruder pull filament during a print, the filament will encircle the buffer wheel, which will simply turn to go along with the extruder pulling. When there is a retract // unload, the filament will be pushed back in the filament cage, making big loops (as much as the cage allows, so roughly 15 cm diameter), storing the filament buffer length in the cage. More filament turns around the wheel implies a longer buffer length. Use 4 turns to form a buffer of around 120 cm. 


**Q: Why not use a spool rewinder instead of a buffer?**  
**A:** Usual rewinders are using either a spring or a counterweight of some sort (nuts, bearing, spool itself...). The result is that it will rewind a certain number of spool turn, not a defined filament length (an almost empty spool will have a very small rewinding capabiliy). Also VORON V1s and V2s are big printers and the reverse bowden is usually quite long (around 80cm), meaning that typical rewinding solutions are not enough anyway. On the other hand, a buffer like the one on the Carrot Patch can handle very long filament buffer length.


**Q: The buffer wheel recess on the buffer cross has a smaller diamater than the buffer wheel itself, is this normal?**  
**A:** Yes. Goal of this recess is just to reduce the total contact surface between the wheel and the buffer cross "wall", while conserving a direct contact with the edge of the wheel.
