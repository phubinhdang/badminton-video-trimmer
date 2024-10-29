```
├── data
│   ├── lanier_qi     
│   |    └── input
│   |    |      └── video.mp3
│   |    |      └── img10fps
│   |    │      |       ├── img_0001.jpg
│   |    │      |       ├── img_0002.jpg
│   |    │      |       ├── ...
│   |    │      ├── badminton_img10fps_info.json
│   |    │      ├── badminton_annotations_with_fps_duration.json
│   |    └── output
│   |    │      ├── summary.mp4
│   |    │      ├── clips.csv
│   |    │      ├── subclips
│   |
```


OLD

```
├── videos
        │        ├── ginting_axelsen_000.mp4    <-- source clips ~180 seconds in 30 fps
        │        ├── ginting_axelsen_001.mp4
        │        ├── ...
        ├── img10fps 
        │    ├── ginting_axelsen_000            <-- sampled images in 10 fps 
        │       ├── img_0001.jpg                  
        │       ├── img_0002.jpg
        │       ├── ... 
        │    ├── ginting_axelsen_002
        │    ├── ...
        ├── badminton_img10fps_info.json        <-- annotation of feature length (number of images) and duration (clip duration in seconds)
        ├── badminton_annotations_with_fps_duration.json   <--  annotation of segements and labels for actions
```

