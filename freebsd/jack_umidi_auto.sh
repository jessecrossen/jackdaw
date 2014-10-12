#!/bin/csh

# jack_umidi_auto.sh
#   this script automatically starts jack_umidi for any plugged-in USB MIDI 
#   devices and continues running to do the same for newly plugged-in devices

# temp files where we store all devices and connected devices to diff them
set target="/tmp/jack_umidi_auto.target"
set current="/tmp/jack_umidi_auto.current"
set commands="/tmp/jack_umidi_auto.commands"
# poll for new devices
while (1)
	# list all devices, swallowing stderr if ls complains that there are none
	(ls /dev/umidi*.0 | sort > "$target") >& /dev/null
	# get all jack_umidi processes
	ps -A -o command | grep 'jack_umidi' | \
		# extract the device name from processes that have one \
		sed -n -e 's~^.*\(/dev/umidi[0-9]*\.0\).*$~\1~p' | sort | uniq > "$current"
	# find devices that aren't represented in the process list
	diff "$current" "$target" | \
		# make commands to start jack_umidi for each one \
		sed -n -e 's/^> \(.*\)$/jack_umidi -C \1 -k -B/p' | \
			#  show commands to be run for transparency \
			tee "$commands"
	# run commands
	/bin/csh "$commands"
	sleep 1
end