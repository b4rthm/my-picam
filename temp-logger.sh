#!/bin/bash
FILE="/home/pi/temperature.log"
rm $FILE
max_temp=0
while true
do
curr_temp=$(vcgencmd measure_temp | sed -r "s/temp=//" | sed -r "s/.[0-9]'C//")
if(($curr_temp > $max_temp)); then
	max_temp=$curr_temp
	max_temp_date=$(date)
fi
{ echo "temp=$curr_temp'C"; date; echo "  max_temp=$max_temp $max_temp_date"; } | tr "\n" " " >> $FILE
echo "" >> $FILE
sleep 60
done
