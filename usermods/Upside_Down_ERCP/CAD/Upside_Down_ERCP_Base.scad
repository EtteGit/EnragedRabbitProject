$fn=30;

difference () {
translate([4,-2.82,2.5]) {
import("../../../Carrot_Patch/STLs/Main_Body.stl");
}

translate([-16,10,0]) {
rotate([0,90,0]) {
cylinder(d=3.3,h=7);
}
}

translate([-16,10,0]) {
rotate([0,90,0]) {
cylinder(d=6,h=3);
}
}
translate([4,-20,-10]) {
cube([20,20,20]);
}
}

