$fn = 30;

// The width of the border in mm
borderWidth = 5;

// The spacing between the mounting holes
// 78 for the ERCF v1.0, 101.172 for the ERCP v1.1
holeSpacing = 101.172;

// The size of the extrusions (only square supported)
extrusionSize = 20;

// Calculates the spacing between both extrusions
extrusionSpacing = holeSpacing - 20;

difference()
    {
        // Bigger outside cube
        cube([ extrusionSize + borderWidth,
               extrusionSize * 2 + extrusionSpacing + borderWidth * 2,
               extrusionSize + borderWidth ]);

        // Smaller inside cube
        translate([borderWidth, borderWidth, borderWidth])
        {
            cube([ extrusionSize,
                   extrusionSize * 2 + extrusionSpacing,
                   extrusionSize ]);
        }

        // Left screw hole, parallel to the extrusion
        translate([ 0,
                    extrusionSize / 2 + borderWidth,
                    extrusionSize / 2 + borderWidth])
        {
            rotate([0, 90, 0])
            {
                cylinder(d = 5.5, h = borderWidth);
            }
        }

        // Left screw hole, perpendicular to the extrusion
        
        translate([ extrusionSize / 2 + borderWidth,
                    0,
                    extrusionSize / 2 + borderWidth])
        {
            rotate([0, 90, 90])
            {
                cylinder(d = 5.5, h = borderWidth);
            }
        }


        // Right screw hole, parallel to the extrusion
        translate([ 0,
                    extrusionSize / 2 + borderWidth + extrusionSpacing + extrusionSize,
                    extrusionSize / 2 + borderWidth])
        {
            rotate([0, 90, 0])
            {
                cylinder(d = 5.5, h = borderWidth);
            }

        }
        
        // Right screw hole, perpendicular to the extrusion
        translate([ extrusionSize / 2 + borderWidth,
                    extrusionSize + borderWidth + extrusionSpacing + extrusionSize,
                    extrusionSize / 2 + borderWidth])
        {
            rotate([0, 90, 90])
            {
                cylinder(d = 5.5, h = borderWidth);
            }

        }
        
        // Left screw hole, bottom of the extrusion
        translate([ extrusionSize / 2 + borderWidth,
                    extrusionSize / 2 + borderWidth,
                    0
                    ])
        {
            rotate([0, 0, 0])
            {
                cylinder(d = 5.5, h = borderWidth);
            }
        }

        // Right screw hole, bottom of the extrusion
        translate([ extrusionSize / 2 + borderWidth,
                    extrusionSize / 2 + borderWidth + extrusionSpacing + extrusionSize,
                    0])
        {
            rotate([0, 0, 0])
            {
                cylinder(d = 5.5, h = borderWidth);
            }
        }
    }
        