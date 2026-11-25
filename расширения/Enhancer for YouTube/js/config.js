/*
##
##  Enhancer for YouTube™
##  =====================
##
##  Author: Max RF <https://www.mrfdev.com>
##
##  This file is protected by copyright laws and international copyright
##  treaties, as well as other intellectual property laws and treaties.
##
##  All rights not expressly granted to you are retained by the author.
##  Read the license.txt file for more details.
##
##  © MRFDEV.com - All Rights Reserved
##
*/
const config={applyvideofilters:!1,backdropcolor:"#000000",backdropopacity:85,blackbars:!1,blockautoplay:!0,blockhfrformats:!1,blockwebmformats:!1,forcevp9:!0,boostvolume:!1,cinemamode:!1,cinemamodewideplayer:!1,controlbar:{active:!1,autohide:!1,centered:!0,position:"absolute"},controls:"speed-minus speed speed-plus screenshot options".split(" "),controlsvisible:!0,controlspeed:!0,controlspeedmousebutton:!1,
controlvolume:!0,controlvolumemousebutton:!1,convertshorts:!1,customcolors:{"--main-color":"#ff0033","--main-background":"#111111","--second-background":"#181818","--hover-background":"#232323","--main-text":"#eff0f1","--dimmer-text":"#cccccc","--shadow":"#000000"},customcss:"",customscript:"",customtheme:!1,darktheme:!1,date:0,defaultvolume:!1,disableautoplay:!1,executescript:!1,expanddescription:!1,filter:"none",griditemsperrow:{channel:{shorts:{apply:!1,count:5},videos:{apply:!0,count:8}},posts:{apply:!1,
count:4},shorts:{apply:!1,count:8},videos:{apply:!0,count:6}},hidecardsendscreens:!1,hidechat:!1,hidecomments:!1,hiderelated:!1,hideshorts:!0,ignoreplaylists:!0,ignorepopupplayer:!0,localecode:"ru",localedir:"ltr",miniplayer:!0,miniplayerposition:"top-left",miniplayersize:"480x270",newestcomments:!1,overridespeeds:!0,pauseforegroundtab:!1,pausevideos:!1,popuplayersize:"640x360",previousversion:"0.0.0",qualityembeds:"medium",qualityembedsfullscreen:"hd1080",qualityplaylists:"hd1440",qualityplaylistsfullscreen:"hd1080",
qualityvideos:"hd1440",qualityvideosfullscreen:"hd1080",reload:!1,reversemousewheeldirection:!1,selectquality:!0,selectqualityfullscreenoff:!1,selectqualityfullscreenon:!1,speed:1.2,speedvariation:.2,stopvideos:!1,theatermode:!1,theme:"enhanced-dark",themevariant:"dark-red.css",update:0,vendorthemevariant:"youtube-deep-dark.css",videofilters:{blur:0,brightness:100,contrast:100,grayscale:0,rotation:0,inversion:0,saturation:100,sepia:0},volume:50,volumemultiplier:2,volumevariation:5,whatsnew:!1,wideplayer:!1,
wideplayerviewport:!1},configEmbed={blockhfrformats:config.blockhfrformats,blockwebmformats:config.blockwebmformats,forcevp9:config.forcevp9,controls:config.controls,controlspeed:config.controlspeed,controlspeedmousebutton:config.controlspeedmousebutton,controlvolume:config.controlvolume,controlvolumemousebutton:config.controlvolumemousebutton,defaultvolume:config.defaultvolume,ignorepopupplayer:config.ignorepopupplayer,localecode:config.localecode,overridespeeds:config.overridespeeds,pausevideos:config.pausevideos,qualityembeds:config.qualityembeds,
qualityembedsfullscreen:config.qualityembedsfullscreen,reversemousewheeldirection:config.reversemousewheeldirection,selectquality:config.selectquality,selectqualityfullscreenoff:config.selectqualityfullscreenoff,selectqualityfullscreenon:config.selectqualityfullscreenon,speed:config.speed,speedvariation:config.speedvariation,volume:config.volume,volumemultiplier:config.volumemultiplier,volumevariation:config.volumevariation},configLiveChat={customcolors:config.customcolors,customcss:config.customcss,
customtheme:config.customtheme,darktheme:config.darktheme,hidechat:config.hidechat,theme:config.theme,themevariant:config.themevariant,vendorthemevariant:config.vendorthemevariant};

// === efyt-defaults: настройки из Яндекс.Браузера как значения по умолчанию ===
// Источник: config-backup.json (14 ключей, снят с профиля Яндекс.Браузера
// 2026-11-16). В CRX-сборке config-backup.json исключён из архива, поэтому
// значения вшиваются сюда и досыпаются в chrome.storage.local сервис-воркером
// только для отсутствующих ключей (пользовательские правки не перетираются).
const defaultChannelSpeeds = {
  "UC0hNui8bT7yV0Xb8w8YxjHw": 1,
  "UC0nW4-kTAhWrlSJkfS-pcjg": 1.5,
  "UC111NXlcDs0VGfyre6EiPmA": 1.75,
  "UC4e_XPBiiIO4fo4_CucxQeg": 1,
  "UC74sX8oY-MVC7_3KzlnFgzQ": 1,
  "UCGq38E3cs6LIpvtl1HBPp9Q": 1.4,
  "UCQBJTVg6csKzQartf8gE4Ow": 1.6,
  "UCTlTfHhcn44XdLn_arCsaig": 1.5,
  "UCYcVUqtQ0Bjl_h9qyWu969Q": 1,
  "UCfV2zYMU3CIAMBtTguqjYzg": 1,
  "UCgpSieplNxXxLXYAzJLLpng": 1.5,
  "UCj9qJBfB7dG9Ab9ldn7pXwQ": 1,
  "UCq3PlGB0_e6jTc9Jr2Al7LQ": 2,
  "UCq9yZoLoSfP3x_cdUmW9SvA": 1.5,
  "UCqmxkrCmLNZfoLZsgweVF7Q": 1,
  "UCwDF_86MbmsQp7cBtgIflJg": 1,
  "UCwZOrfqqqY5Ku5c0gUstvwA": 1.5,
  "UCwjhNxiTk2mSGTtmIixDXpQ": 1,
  "UCxjs3aUQ9OnufZQZaCH-E4w": 1,
  "UCxn_odPreZlRXtf63vtj1vw": 1,
  "UCyRtVkSY1doj5Pu6NxnCGJA": 1.4,
  "name:AIA Podcast": 1,
  "name:Apostle Dmytro Karpenko": 1.5,
  "name:Better Voice": 2,
  "name:BuildWithAI": 1,
  "name:Dailyhardcore": 1.5,
  "name:DenTrave": 1.5,
  "name:Epic Legacy Trailer Music": 1,
  "name:IXBT Games": 1,
  "name:Ivan Yakovina": 1.4,
  "name:ModjoOfficial": 1,
  "name:Poets of the Fall (Official)": 1,
  "name:SERGiO Go": 1,
  "name:Tymlex": 1,
  "name:zWORMz Gaming": 1,
  "name:ИИ Новости": 1.5,
  "name:Киряша": 1,
  "name:Майкл Наки": 1.5,
  "name:Олег Жданов": 1.75,
  "name:ФЕЙГИН SHORTS": 1.6,
  "name:Юрий ВЕЛИКИЙ": 1,
  "name:ЯБ ПОИГРАЛ": 1.4
};
const defaultSettings = {
  channelspeeds: defaultChannelSpeeds,
  controlbar: config.controlbar,
  controls: config.controls,
  controlsvisible: config.controlsvisible,
  forcevp9: config.forcevp9,
  griditemsperrow: config.griditemsperrow,
  hideshorts: config.hideshorts,
  maTheme: "dark",
  qualityplaylists: config.qualityplaylists,
  qualityvideos: config.qualityvideos,
  selectquality: config.selectquality,
  speed: config.speed
};