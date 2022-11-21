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
        echo "Klipper service not found! pleasP install Klipper first"
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
            echo "Config file ${dest} already exists - moving old to ${file}.00"
	    mv ${dest} ${dest}.00
        fi
	# A little simplistic at the moment...
        if [ "${file}" == "ercf_hardware.cfg" ]; then
            if [ "${sensorless_selector}" -eq 1 ]; then
                cat ${SRCDIR}/${file} | sed -e "\
                    s/^#endstop_pin: \^ercf:PB9/!endstop_pin: \^ercf:PB9/; \
                    s/^#diag_pin: \^ercf:PA7/diag_pin: \^ercf:PA7/; \
                    s/^#driver_SGTHRS: 75/driver_SGTHRS: 75/; \
		    s/^endstop_pin: \^ercf:PB9/#endstop_pin: \^ercf:PB9/; \
                    s/^!endstop_pin: \^ercf:PB9/endstop_pin: \^ercf:PB9/; \
                    s/^#endstop_pin: tmc2209_selector_stepper/endstop_pin: tmc2209_selector_stepper/; \
                        " > ${dest}
            else
                # This is the default template config
                cp ${SRCDIR}/${file} ${dest}
            fi
	else
            cat ${SRCDIR}/${file} | sed -e "\
                s/{sensorless_selector}/${sensorless_selector}/g; \
                s/{clog_detection}/${clog_detection}/g; \
                s/{endless_spool}/${endless_spool}/g; \
                    " > ${dest}
	fi
    done
}

install_update_manager() {
    echo "Adding update manager to moonraker.conf"
    update_section=$(grep -c '\[update_manager ercf-happy_hare\]' \
    ${KLIPPER_CONFIG_HOME}/moonraker.conf || true)
    if [ "${update_section}" -eq 0 ]; then
        echo "" >> ${KLIPPER_CONFIG_HOME}/moonraker.conf
        while read -r line; do
            echo -e "${line}" >> ${KLIPPER_CONFIG_HOME}/moonraker.conf
        done < "${SRCDIR}/moonraker_update.txt"
        echo "" >> ${KLIPPER_CONFIG_HOME}/moonraker.conf
    else
        echo "[update_manager ercf] already exist in moonraker.conf - skipping install"
    fi
}

restart_klipper() {
    echo "Restarting Klipper..."
    sudo systemctl restart klipper
}

prompt_yn() {
    while true; do
	    read -p "$@ (y/n)?" yn
        case "${yn}" in
            Y|y|Yes|yes|"")
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
check_klipper
link_ercf_plugin

if [ "${INSTALL_TEMPLATES}" -eq 1 ]; then
    easy_brd=0
    sensorless_selector=0
    clog_detection=0
    endless_spool=0
    echo
    echo "Let me see if I can help you with initial config (you will still have some manual config to perform)..."
    echo
    yn=$(prompt_yn "Are you using the EASY-BRD")
    case $yn in
        y)
            echo
            echo "Sensorless selector operation? This allows for additional selector recovery steps but disables the 'extra' input on the EASY-BRD."
            yn=$(prompt_yn "Enable sensorless selector operation")
            echo
            case $yn in
                y)
	            echo "IMPORTANT: Set the J6 jumper pins to 1-2 and 3-4, i.e. [..][..].  MAKE A NOTE NOW!!"
	            sensorless_selector=1
                    ;;
                n)
	            echo "IMPORTANT: Set the J6 jumper pins to 1-2 and 4-5, i.e. [..].[..]  MAKE A NOTE NOW!!"
	            sensorless_selector=0
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
            echo "Endless spool? This uses filament runout detection to automate switching to new spool without interruption"
            yn=$(prompt_yn "Enable Endless Spool")
            case $yn in
                y)
                    endless_spool=1
                    ;;
                n)
                    ;;
	    esac
	    echo
	    echo "NOTES:"
	    echo " * Toolhead sensor use will be dependent on your manual configuration"
	    echo " What still needs to be done:"
	    echo " * Find and set your serial_id for EASY-BRD mcu"
	    echo " * Adjust motor speeds and current if using NEMA 17 motors"
	    echo " * Adjust your config for loading and unloading preferences"
	    echo " * Adjust distances (bowden length & extruder) for you particular setup"
	    echo 
	    echo "Good luck! ERCF is complex to setup. Remember Discord is your friend.."
	    echo
            ;;

        n)
            echo "Sorry, I only support the EASY-BRD setup at the moment"
            echo
	    easy_brd=0
	    ;;
    esac
    copy_template_files
    echo
fi

install_update_manager
restart_klipper

