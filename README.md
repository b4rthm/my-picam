# my-picam

## create systemd services (or copy mine) and reload

    sudo nano /etc/systemd/system/start_server.service
    sudo nano /etc/systemd/system/start_makeFoto.service

    sudo systemctl enable start_server.service
    sudo systemctl enable start_makeFoto.service
    sudo systemctl start start_server.service
    sudo systemctl start start_makeFoto.service

    sudo systemctl daemon-reload

## startup for temp logger

    chmod +x /home/pi/my-picam/temp-logger.sh 

    sudo nano /etc/rc.local

Add this line: 
    
    sudo /home/pi/my-picam/temp-logger.sh &

## useful aliases 

    alias enableServices="sudo systemctl enable start_server.service && sudo systemctl enable start_makeFoto.service"
    alias disableServices="sudo systemctl disable start_server.service && sudo systemctl disable start_makeFoto.service"
    alias startServices="sudo systemctl start start_server.service && sudo systemctl start start_makeFoto.service"
    alias stopServices="sudo systemctl stop start_server.service && sudo systemctl stop start_makeFoto.service"

## check ip

    hostname -I

## routes

1. /
2. /info
3. /refresh
4. /timelapse?fps=3
   
