import numpy as np
import pandas as pd


class SegmentMerger(object):
    def __init__(self, video_dict=None):
        self.video_dict = video_dict
        self.all_pred = []

    def update(self, pred):
        pred_numpy = {
            k: {kk: vv.detach().cpu().numpy() for kk, vv in v.items()}
            for k, v in pred.items()
        }
        for k, v in pred_numpy.items():
            # pdb.set_trace()
            if "window" not in k:
                this_dets = [
                    [
                        v["segments"][i, 0],
                        v["segments"][i, 1],
                        v["scores"][i],
                        v["labels"][i],
                    ]
                    for i in range(len(v["scores"]))
                ]
                video_id = k
            else:
                window_start = self.video_dict[k]["time_offset"]
                video_id = self.video_dict[k]["src_vid_name"]
                this_dets = [
                    [
                        v["segments"][i, 0] + window_start,
                        v["segments"][i, 1] + window_start,
                        v["scores"][i],
                        v["labels"][i],
                    ]
                    for i in range(len(v["scores"]))
                ]
        this_dets = np.array(this_dets)
        input_dets = np.copy(this_dets)
        sort_idx = input_dets[:, 2].argsort()[::-1]
        dets = input_dets[sort_idx, :]
        dets = dets[:200, :]
        dets[:, 3] = 0  # binary

        # self.all_pred = {k: [] for k in self.nms_mode}
        self.all_pred += [[video_id, k] + det for det in dets.tolist()]

    def dump_detection_to_json(self, save_path):
        df = pd.DataFrame(
            self.all_pred,
            columns=["video-id", "slice-id", "start", "end", "score", "cls"],
        )
        df[['start', 'end', 'score']].to_csv(save_path)