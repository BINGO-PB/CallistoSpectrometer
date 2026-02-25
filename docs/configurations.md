# Configuration Files and Modes


- COnsiderando o código deste projeto, um port de codigo ooriginal em C, vamos tornr a estrtura mais em sintonia com o ambiente de desenvolvimento da colaboração BINGO, mas garantindo a operabilidade standalone típica do spectrometro callisto.

- O programa deve permitir instalação por usuário comum linux, sem sudo.
- CLI disponível inicia um servidor tcp para receber comandos
- A interação do programa com o dispositivo é por servidor serial async
- O usuário deve ser capaz de mudar o modo de funcionamento interagindo via tcp, podendo mudar os modos de medida.
- Vamos prover um script para instalação via systemd.user
- A configuração (ou comandos que a sobreponham) permite selecionar a criação de arquivos FITS ou HDF5
- É possívewl colocar o programa em modo de stream de dados via zmq
- O programa detecta a presença da unidade de calibração e passa comandos para ela via porta serial por meio de um plugin
- modo gui com botões para selecionar START STOP OVS FITS HDF5 com painel de visualização dos dados.

## Measurement Mode

| Code | Measurement mode |
|-------|-------------------|
|0|Stop actual mode, go to idle. No data will be stored. Scheduler waits for another entry to be applied to Callisto|
|1|Spare code
|2|Calibration mode. Save measured data to local disc, calibrated in SFU. Storage is compressed as 45*log(S+10). Calibration parameter file needed!
|3|Continuous recording or steady mode. Sampled data are stored without calibration on local disc in raw format (digits) 8 bit resolution. This, according to configuration - and frequency - file.
|4|Spectral overview continous mode every 60s
|5|Spare code
|6|Spare code
|7|Terminate application program, go back to operating system (dangerous, therefore disabled within e-Callisto)
|8|Automatic spectral overview OV for periodic radio monitoring (CRAF)
|9|Spare code


## Configuration

```bash
#callisto.cfg
[rxcomport]=/dev/ttyUSB0
[calpost]=/dev/ttyACM0
[rxbaudrate]=115200
[observatory]=12 #Callisto Do not Change
[instrument]= BINGO
[titlecomment]=LHCP
[origin]=
[longitude]=E,8.1122155
[latitude]=N,47.3412278
[height]=416.5
[clocksource]=1 # RISC-level: 1=internal, 2=external, default=1
[filetime]=900 # time periode for one single raw-file (in seconds)
[frqfile]=frq00201.cfg # default frequency program
[focuscode]=59 # default focuscode (00 … 63)
[mmode]=3 # default continuous recording
[timerinterval]=30 # global timing interval [msec] , fixed
[timerpreread]=2 # timer to prepare stop-process via scheduler, fixed
[timeouthexdata]=1000 # timer to empty all buffers after stop, fixed
[fitsenable]=1 # 0=no FITSfile, 1=FITS write On
[datapath]=c:\test\ # default datafile path
[logpath]=c:\test\ # default logfile path
[low_band]=171.0 # VHF band III barrier (MHz), fixed
[mid_band]=450.0 # UHF band IV barrier (MHz), fixed
[chargepump]=1 # charge pump: 0=false=off, 1=true=on=default
[agclevel]=150 # PWM level for tuner AGC 50...255, default 120
[detector_sens]=25.4 # detector sensitivity mV/dB, default 25.4
[autostart]=0
[outputformat]=fits
# ZMQ PUB (opcional): publicar frames para consumo externo (ex.: KUNLUN)
# Alternativa: exportar env var CALLISTO_ZMQ_PUB_ENDPOINT
[zmq_pub_endpoint]=tcp://*:5556
[zmq_pub_bind]=1
[zmq_pub_topic]=callisto
[zmq_pub_hwm]=10
```

```bash 
# scheduler.cfg
04:00:00,59,3   // iniciar aquisição
12:00:00,59,8   // overview
19:30:00,59,0   // parar aquisição
```

## FITs File Header

SIMPLE =
T / file does conform to FITS standard
BITPIX =
16 / number of bits per data pixel
NAXIS
=
2 / number of data axes
NAXIS1 =
631 / length of data axis 1
NAXIS2 =
200 / length of data axis 2
EXTEND =
T / FITS dataset may contain extensions
COMMENT = 'Warning: the value of CDELT1 may be rounded!'
COMMENT = 'Warning: the frequency axis may not be regular!'
COMMENT = 'Warning: the value of CDELT2 may be rounded!'
COMMENT = '
'
/ empty comment
DATE
= '2004-12-06'
/ Time of observation
CONTENT = '2004/12/06 Radio flux density (BLEN5M)' / Title of image
ORIGIN = 'ETH Zurich Switzerland' / Organization name
TELESCOP = 'Radio Spectrometer' / Type of instrument
INSTRUME = 'LAB
'
/ Name of the spectrometer
OBJECT = 'Sun'
/ object description
DATE-OBS = '2004/12/06'
/ Date observation starts
TIME-OBS = '12:45:23.382'
/ Time observation starts
DATE-END = '2004/12/06'
/ date observation ends
File: eCallistoManual.doc
Page: 13/37
Created on 23/10/2006 4:04 PMETH
CALLISTO
Operating Manual
TIME-END = '12:50:38'
/ time observation ends
BZERO =
0. / scaling offset
BSCALE =
1. / scaling factor
BUNIT
= 'digits '
/ z-axis title
DATAMIN =
0 / minimum element in image
DATAMAX =
255 / maximum element in image
CRVAL1 =
45923. / value on axis 1 at reference pixel [sec]
CRPIX1 =
0 / reference pixel of axis 1
CTYPE1 = 'Time [UT]' / title of axis 1
CDELT1 =
0.5 / step between first and second element in
x-axis
CRVAL2 =
200. / value on axis 2 at the reference pixel
CRPIX2 =
0 / reference pixel of axis 2
CTYPE2 = 'Frequency [MHz]' / title of axis 2
CDELT2 =
-1. / step between first and second element in
axis
HISTORY = '
'
OBS_LAT =
47.3412284851074 / observatory latitude in degree
OBS_LAC = 'N
'
/ observatory latitude code {N,S}
OBS_LON =
8.11221504211426 / observatory longitude in degree
OBS_LOC = 'E
'
/ observatory longitude code {E,W}
OBS_ALT =
416.5 / observatory altitude in meter asl
FRQFILE = FRG0021.CFG / name of the frequency file
PWM_VAL = 120 / pwm-value to control tuner gain voltage
END



| Command to control calibration unit | Effect |
|-------------------------------------|--------|
|V?         |Sends current software version to the host|
|RESET      |Arduino soft reset |
|U28        |Measures supply voltage of noise source + relays|
|tcu        |Measures and shows temperature of cold plate|
|UR         |Measures return contact voltage of RF-relays|
|debug0     |Switches off debug information|
|debug1     |Activates printing of debug information|
|echo0      |Switches off command echo|
|echo1      |Activates echoing of commands|
|Tcold      |Switches calibration unit to A2 (reference)                |
|Tsky       |Switches calibration unit to A1 (antenna)  |
|Twarm      |Switches calibration to noise source +5 dB ENR |
|Thot       |Switches calibration to noise source +15 dB ENR    |
|TestX      |Switches all RF-relays into position J1    |
|TestY      |Switches all RF-relays into position J2    |
|Pheat      |Switches Peltier system into heating   |
|Pcool      |Switches Peltier system into cooling   |
|Poff       |Switches Peltier power off|
|con1       |Temperature control automatic on|
|con0           |Temperature control automatic off  |
|Tnom%f     |Set nominal temperature, e.g. Tnom300 [K]  |
|Ttol%f     |Set tolerance (+/-) for temperature control [K]    |
|Rest       |Illegal command -> error message|

|Focus code - Observation modes | Description |
|---------------|-------|
|01|Tcold (50Ω) at port A2
|02|Twarm (+5 dB ENR)
|03|Thot (+15 dB ENR)
|04|Tsky during calibration at port A1
|00, 05…..63|Tsky during regular observation (default 04)













