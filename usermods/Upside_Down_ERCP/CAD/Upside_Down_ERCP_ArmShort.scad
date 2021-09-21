$fn=60;

vOffset = 3.5;

translate([-13,-2.5,14]) {
cube([5,5,10]);
}

translate([-12.5,-6.5,21.65]) {
cube([15,13,1]);
}

translate([-3,-6.5,18.65]) {
cube([5,13,3]);
}

difference() {
union () {
difference () {
translate([0,-6.5,0]) {
import("../../../Carrot_Patch/STLs/Spool_Arm.stl");
}

translate([-13,0,10]) {
rotate([0,90,0]) {
    cylinder(d=4.5,h=4.3);
}
}


translate([0,-10,0]) {
cube([150,20,30]);
}
}

translate([0,-6.5,0]) {

//cube([4,13,12]);
}
difference() {
    translate([0,0,29+vOffset]) {
rotate([180,0,0]) {
difference() {
translate([0,-6.5,0]) {
import("../../../Carrot_Patch/STLs/Spool_Arm.stl");
}
translate([-20,-10,0]) {
cube([20,20,40]);
}
}
}
}
translate([0,-10,-10]) {
cube([250,20,10]);
}

}
}


translate([-7,0,8.25+vOffset]) {
rotate([0,90,0]) {
cylinder(d=4.3,h=120);
}
}

translate([0,-6.5,0]) {
translate([0,0,0]) {
cube([75,13,8]);
}
}


translate([-15,-10,32.5]) {
cube([20,20,20]);
}

translate([-10,-8,22.65]) {
cube([5,5,20]);
}

translate([-10,3,22.65]) {
cube([5,5,20]);
}

}
