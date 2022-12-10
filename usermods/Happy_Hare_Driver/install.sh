#!/bin/bash
KLIPPER_HOME="${HOME}/klipper"
KLIPPER_CONFIG_HOME="${HOME}/klipper_config"

verify_not_root() {
    if [ "$EUID" -eq 0 ]; then
        echo "This script must not run as root"
        exit -1
    fi
}

check_klipper() {
    if [ "$(sudo systemctl list-units --full -all -t service --no-legend | grep -F "klipper.service")" ]; then
        echo "Klipper service found"
    else
        echo "Klipper service not found! Please install Klipper first"
        exit -1
    fi

}

verify_home_dirs() {
    if [ ! -d "${KLIPPER_HOME}" ]; then
        echo "Klipper home directory (${KLIPPER_HOME}) not found. Use '-k <dir>' option to override"
        exit -1
    fi
    if [ ! -d "${KLIPPER_CONFIG_HOME}" ]; then
        echo "Klipper config directory (${KLIPPER_CONFIG_HOME}) not found. Use '-c <dir>' option to override"
        exit -1
    fi
}

link_ercf_plugin() {
    echo "Linking ercf extension to Klipper..."
    ln -sf "${SRCDIR}/extras/ercf.py" "${KLIPPER_HOME}/klippy/extras/ercf.py"
}

copy_template_files() {
    echo "Copying configuration files to ${KLIPPER_CONFIG_HOME}"
    for file in `cd ${SRCDIR} ; ls *.cfg`; do
        dest=${KLIPPER_CONFIG_HOME}/${file}

        if test -f $dest; then
            echo "Config file ${dest} already exists - moving old one to ${file}.00"
	    mv ${dest} ${dest}.00
        fi

        if [ "${easy_brd}" -eq 1 ]; then
            if [ "${file}" = "ercf_hardware.cfg" ]; then
                if [ "${toolhead_sensor}" -eq 1 ]; then
                    magic_str1="## ERCF Toolhead sensor"
                else
                    magic_str1="NO TOOLHEAD"
		fi
                if [ "${clog_detection}" -eq 1 ]; then
                    magic_str2="## ERCF Clog detection"
                else
                    magic_str2="NO CLOG"
		fi

                if [ "${sensorless_selector}" -eq 1 ]; then
                    cat ${SRCDIR}/${file} | sed -e "\
                        s/^#endstop_pin: \^ercf:PB9/!endstop_pin: \^ercf:PB9/; \
                        s/^#diag_pin: \^ercf:PA7/diag_pin: \^ercf:PA7/; \
                        s/^#driver_SGTHRS: 75/driver_SGTHRS: 75/; \
                        s/^endstop_pin: \^ercf:PB9/#endstop_pin: \^ercf:PB9/; \
                        s/^!endstop_pin: \^ercf:PB9/endstop_pin: \^ercf:PB9/; \
                        s/^#endstop_pin: tmc2209_selector_stepper/endstop_pin: tmc2209_selector_stepper/; \
                        s%{serial}%${serial}%; \
                        s/{toolhead_sensor_pin}/${toolhead_sensor_pin}/; \
                        /^${magic_str1} START/,/${magic_str1} END/ s/^#//; \
                        /^${magic_str2} START/,/${magic_str2} END/ s/^#//; \
                            " > ${dest}
                else
                    # This is the default template config
                    cat ${SRCDIR}/${file} | sed -e "\
                        s%{serial}%${serial}%; \
                        s/{toolhead_sensor_pin}/${toolhead_sensor_pin}/; \
                        /^${magic_str1} START/,/${magic_str1} END/ s/^#//; \
                        /^${magic_str2} START/,/${magic_str2} END/ s/^#//; \
                            " > ${dest}
                fi
            elif [ "${file}" = "ercf_software.cfg" ]; then
                cat ${SRCDIR}/${file} | sed -e "\
                    s%{klipper_config_home}%${KLIPPER_CONFIG_HOME}%g; \
                        " > ${dest}
	    else
                # Not ercf_hardware.cfg or ercf_software.cfg
                cat ${SRCDIR}/${file} | sed -e "\
                    s/{sensorless_selector}/${sensorless_selector}/g; \
                    s/{clog_detection}/${clog_detection}/g; \
                    s/{endless_spool}/${endless_spool}/g; \
                    s/{servo_up_angle}/${servo_up_angle}/g; \
                    s/{servo_down_angle}/${servo_down_angle}/g; \
                    s/{calibration_bowden_length}/${calibration_bowden_length}/g; \
                        " > ${dest}
            fi
        else
            # Non EASY-BRB just install most of the templates as is
            if [ "${file}" = "ercf_software.cfg" ]; then
                cat ${SRCDIR}/${file} | sed -e "\
                    s%{klipper_config_home}%${KLIPPER_CONFIG_HOME}%g; \
                        " > ${dest}
            else
                cp ${SRCDIR}/${file} ${dest}
            fi
        fi
    done
}

install_update_manager() {
    echo "Adding update manager to moonraker.conf"
    if [ -f "${KLIPPER_CONFIG_HOME}/moonraker.conf" ]; then
        update_section=$(grep -c '\[update_manager ercf-happy_hare\]' \
        ${KLIPPER_CONFIG_HOME}/moonraker.conf || true)
        if [ "${update_section}" -eq 0 ]; then
            echo "" >> ${KLIPPER_CONFIG_HOME}/moonraker.conf
            while read -r line; do
                echo -e "${line}" >> ${KLIPPER_CONFIG_HOME}/moonraker.conf
            done < "${SRCDIR}/moonraker_update.txt"
            echo "" >> ${KLIPPER_CONFIG_HOME}/moonraker.conf
            restart_moonraker
        else
            echo "[update_manager ercf] already exist in moonraker.conf - skipping install"
        fi
    else
        echo "Moonraker.conf not found!"
    fi
}

restart_klipper() {
    echo "Restarting Klipper..."
    sudo systemctl restart klipper
}

restart_moonraker() {
    echo "Restarting Moonraker..."
    sudo systemctl restart moonraker
}

prompt_yn() {
    while true; do
        read -p "$@ (y/n)?" yn
        case "${yn}" in
            Y|y|Yes|yes)
		echo "y" 
                break;;
            N|n|No|no)
		echo "n" 
    	        break;;
    	    *)
		;;
        esac
    done
}

# Force script to exit if an error occurs
set -e
clear

# Find SRCDIR from the pathname of this script
SRCDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/ && pwd )"

INSTALL_TEMPLATES=0
while getopts "k:c:i" arg; do
    case $arg in
        k) KLIPPER_HOME=$OPTARG;;
        c) KLIPPER_CONFIG_HOME=$OPTARG;;
        i) INSTALL_TEMPLATES=1;;
    esac
done

verify_not_root
verify_home_dirs
check_klipper
link_ercf_plugin

easy_brd=0
if [ "${INSTALL_TEMPLATES}" -eq 1 ]; then
    echo
    echo "Let me see if I can help you with initial config (you will still have some manual config to perform)..."
    echo
    yn=$(prompt_yn "Are you using the EASY-BRD")
    case $yn in
        y)
            easy_brd=1
            serial=""
            echo
            for line in `ls /dev/serial/by-id | grep "Klipper_samd21"`; do
                echo "Is this your EASY-BRD serial port?"
		yn=$(prompt_yn "/dev/serial/by-id/${line}")
                case $yn in
                    y)
                        serial="/dev/serial/by-id/${line}"
			break
                        ;;
                    n)
                        ;;
                esac
            done
            if [ "${serial}" = "" ]; then
                echo "Couldn't find your serial port, but no worries - I'll configure the default and you can manually change later as per the docs"
                serial='/dev/ttyACM1 # Config guess. Run ls -l /dev/serial/by-id and set manually'
	    fi

            echo
            echo "Do you have a toolhead sensor you would like to use? If reliable this provides the smoothest and most reliable loading and unloading operation"
            yn=$(prompt_yn "Enable toolhead sensor")
            case $yn in
                y)
	            toolhead_sensor=1
	            echo "    What is the mcu pin name that your toolhead sensor is connected too?"
		    echo "    If you don't know just hit return, I can enter a default and you can change later"
                    read -p "    Toolhead sensor pin name? " toolhead_sensor_pin
                    if [ "${toolhead_sensor_pin}" == "" ]; then
                        toolhead_sensor_pin="<dummy_pin_must_set_me>"
                    fi
                    ;;
                n)
	            toolhead_sensor=0
                    toolhead_sensor_pin="<dummy_pin_must_set_me>"
                    ;;
	    esac

            echo
            echo "Sensorless selector operation? This allows for additional selector recovery steps but disables the 'extra' input on the EASY-BRD."
            yn=$(prompt_yn "Enable sensorless selector operation")
            case $yn in
                y)
                    echo
	            echo "    IMPORTANT: Set the J6 jumper pins to 2-3 and 4-5, i.e. .[..][..]  MAKE A NOTE NOW!!"
	            sensorless_selector=1
                    ;;
                n)
                    echo
	            echo "    IMPORTANT: Set the J6 jumper pins to 1-2 and 4-5, i.e. [..].[..]  MAKE A NOTE NOW!!"
	            sensorless_selector=0
                    ;;
	    esac

            echo
	    echo "Using default MG-90S servo? (If you answer no, will setup for Savox SH0255MG - you can change later)"
            yn=$(prompt_yn "MG-90S Servo?")
            case $yn in
                y)
	            servo_up_angle=30
	            servo_down_angle=140
                    ;;
                n)
	            servo_up_angle=140
	            servo_down_angle=30
                    ;;
	    esac

	    echo
            echo "Clog detection? This uses the ERCF encoder movement to detect clogs and can call your filament runout logic"
            yn=$(prompt_yn "Enable clog detection")
            case $yn in
                y)
                    clog_detection=1
                    ;;
                n)
                    clog_detection=0
                    ;;
	    esac

	    echo
            echo "EndlessSpool? This uses filament runout detection to automate switching to new spool without interruption"
            yn=$(prompt_yn "Enable EndlessSpool")
            case $yn in
                y)
                    endless_spool=1
                    if [ "${clog_detection}" -eq 0 ]; then
                        echo
                        echo "    NOTE: I've re-enabled clog detection which is necessary for EndlessSpool to function"
                        clog_detection=1
                    fi
                    ;;
                n)
		endless_spool=0
                    ;;
	    esac

	    echo
	    echo "What is the length of your reverse bowden tube in mm?"
            echo "(This is just to speed up calibration and needs to be approximately right but not longer than the real length)"
            while true; do
                read -p "Reverse bowden length in mm? " calibration_bowden_length
		if ! [ "${calibration_bowden_length}" -ge 1 ] 2> /dev/null ;then
                    echo "Positive integer value only"
                else
                    break
                fi
            done
            ;;

        n)
            echo "Sorry, I only support the EASY-BRD setup at the moment"
	    ;;
    esac


    echo
    echo
    echo "    vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv"
    echo
    echo "    NOTES:"
    echo "     What still needs to be done:"
    if [ "${easy_brd}" -eq 0 ]; then
        echo "     * Edit *.cfg files and substitute all \${xxx} tokens to match your setup"
    else
        echo "     * Tweak motor speeds and current, especially if using non BOM motors"
        echo "     * Adjust motor direction with '!' on pin if necessary. No way to know here"
    fi
    echo "     * Adjust your config for loading and unloading preferences"
    echo "     * Adjust toolhead distances 'home_to_extruder' for your particular setup"
    echo 
    echo "    Good luck! ERCF is complex to setup. Remember Discord is your friend.."
    echo
    echo "    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
    echo

fi

copy_template_files
install_update_manager
restart_klipper
