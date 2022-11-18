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

copy_config_files() {
    echo "Copying configuration files to ${KLIPPER_CONFIG_HOME}"
    for file in `cd ${SRCDIR} ; ls *.cfg`; do
        dest=${KLIPPER_CONFIG_HOME}/${file}
        if test -f $dest; then
            echo "Config file ${dest} already exists - creating ${file}.template"
	    cp ${SRCDIR}/${file} ${dest}.template
        else
	    cp ${SRCDIR}/${file} ${dest}
        fi
    done
}

install_update_manager() {
    echo "Adding update manager to moonraker.conf"
    update_section=$(grep -c '\[update_manager ercf\]' \
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

# Force script to exit if an error occurs
set -e

# Find SRCDIR from the pathname of this script
SRCDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/ && pwd )"

while getopts "k:c:" arg; do
    case $arg in
        k) KLIPPER_HOME=$OPTARG;;
        c) KLIPPER_CONFIG_HOME=$OPTARG;;
    esac
done

verify_not_root
check_klipper
link_ercf_plugin
copy_config_files
install_update_manager
restart_klipper

