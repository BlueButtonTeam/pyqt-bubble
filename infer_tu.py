from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np

import os
import sys
import json
# from  numba import cuda
import psutil
import time
import logging

__dir__ = os.path.dirname(os.path.abspath(__file__))
sys.path.append(__dir__)
sys.path.insert(0, os.path.abspath(os.path.join(__dir__, '..')))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ocr_performance.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

os.environ["FLAGS_allocator_strategy"] = 'auto_growth'
os.environ["CUDA_VISIBLE_DEVICES"]="1"
import paddle
import subprocess
import tracemalloc
from ppocr.data import create_operators, transform
from ppocr.modeling.architectures import build_model
from ppocr.postprocess import build_post_process
from ppocr.utils.save_load import load_model
from ppocr.utils.utility import get_image_file_list
# import tools.program as program
import cv2
import yaml
# import ocr as ocr_check
from collections import Counter
from itertools import zip_longest
from concurrent.futures import ProcessPoolExecutor
# try:
#     from OCR_TOOL import ocr as ocr_check
# except:
#     from .OCR_TOOL import ocr as ocr_check
os.environ["CUDA_VISIBLE_DEVICES"] = "1"
def draw_det_res(dt_boxes, config, img, img_name, save_path):
    
    src_im = img
    for box in dt_boxes:
        box = np.array(box).astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(src_im, [box], True, color=(255, 255, 0), thickness=2)
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    save_path = os.path.join(save_path, os.path.basename(img_name))
    cv2.imwrite(save_path, src_im)

def load_config(file_path):
    """
    Load config from yml/yaml file.
    Args:
        file_path (str): Path of the config file to be loaded.
    Returns: global config
    """
    _, ext = os.path.splitext(file_path)
    assert ext in ['.yml', '.yaml'], "only support yaml files for now"
    config = yaml.load(open(file_path, 'rb'), Loader=yaml.Loader)
    return config

def merge_config(config, opts):
    """
    Merge config into global config.
    Args:
        config (dict): Config to be merged.
    Returns: global config
    """
    for key, value in opts.items():
        if "." not in key:
            if isinstance(value, dict) and key in config:
                config[key].update(value)
            else:
                config[key] = value
        else:
            sub_keys = key.split('.')
            assert (
                sub_keys[0] in config
            ), "the sub_keys can only be one of global_config: {}, but get: " \
               "{}, please check your running command".format(
                config.keys(), sub_keys[0])
            cur = config[sub_keys[0]]
            for idx, sub_key in enumerate(sub_keys[1:]):
                if idx == len(sub_keys) - 2:
                    cur[sub_key] = value
                else:
                    cur = cur[sub_key]
    return config

class Detection:
    def __init__(self, config_path):
        # self.config, self.device, self.logger, self.vdl_writer = self.program.preprocess()
        self.config = load_config(config_path)
        self.global_config = self.config['Global']
    
    def load_checkpoint(self):
        print("开始加载检测模型...")
        start_time = time.time()
        
        self.model = build_model(self.config['Architecture'])

        load_model(self.config, self.model)
        # build post process
        self.post_process_class = build_post_process(self.config['PostProcess'])
        self.transforms = []
        for op in self.config['Eval']['dataset']['transforms']:
            op_name = list(op)[0]
            if 'Label' in op_name:
                continue
            elif op_name == 'KeepKeys':
                op[op_name]['keep_keys'] = ['image', 'shape']
            self.transforms.append(op)
        self.ops = create_operators(self.transforms, self.global_config)
        self.model.eval()
        
        end_time = time.time()
        print(f"检测模型加载完成，耗时: {end_time - start_time:.2f}秒")
    
    def _predict2box(self, img):
        data = {'image': img}
        batch = transform(data, self.ops)

        images = np.expand_dims(batch[0], axis=0)
        shape_list = np.expand_dims(batch[1], axis=0)
        images = paddle.to_tensor(images)
        preds = self.model(images)
        post_result = self.post_process_class(preds, shape_list)
        boxes = post_result[0]['points']
        return boxes
            
            
    def predict(self, img_list):
        print(f"开始文本定位，处理图像数量: {len(img_list)}")
        start_time = time.time()
        
        img_box = []
        for img_data in img_list:
            h,w = img_data.shape[:2]
            _, encoded_image = cv2.imencode(".jpg", img_data)
            img = encoded_image.tobytes()
            box = self._predict2box(img)
            img_box.append(box)

        end_time = time.time()
        print(f"文本定位完成，耗时: {end_time - start_time:.2f}秒")
        return img_box

class OCR_rec:
    def __init__(self, config_path):
        # self.config, self.device, self.logger, self.vdl_writer = self.program.preprocess()
        self.config = load_config(config_path)
        self.global_config = self.config['Global']
    
    def predict_bbox(self, img_list,bbox):
        for idx,img_data in enumerate(img_list):   #get_image_file_list(img_path):
            try:
                _, encoded_image = cv2.imencode(".jpg", img_data)
            except:
                # print(len(img_data))
                # print(img_data)
                continue
            img = encoded_image.tobytes() 
            data = {'image': img}
            batch = transform(data, self.ops)
            if self.config['Architecture']['algorithm'] == "SRN":
                encoder_word_pos_list = np.expand_dims(batch[1], axis=0)
                gsrm_word_pos_list = np.expand_dims(batch[2], axis=0)
                gsrm_slf_attn_bias1_list = np.expand_dims(batch[3], axis=0)
                gsrm_slf_attn_bias2_list = np.expand_dims(batch[4], axis=0)

                others = [
                    paddle.to_tensor(encoder_word_pos_list),
                    paddle.to_tensor(gsrm_word_pos_list),
                    paddle.to_tensor(gsrm_slf_attn_bias1_list),
                    paddle.to_tensor(gsrm_slf_attn_bias2_list)
                ]
            if self.config['Architecture']['algorithm'] == "SAR":
                valid_ratio = np.expand_dims(batch[-1], axis=0)
                img_metas = [paddle.to_tensor(valid_ratio)]
            if self.config['Architecture']['algorithm'] == "RobustScanner":
                valid_ratio = np.expand_dims(batch[1], axis=0)
                word_positons = np.expand_dims(batch[2], axis=0)
                img_metas = [
                    paddle.to_tensor(valid_ratio),
                    paddle.to_tensor(word_positons),
                ]
            if self.config['Architecture']['algorithm'] == "CAN":
                image_mask = paddle.ones(
                    (np.expand_dims(
                        batch[0], axis=0).shape), dtype='float32')
                label = paddle.ones((1, 36), dtype='int64')
            images = np.expand_dims(batch[0], axis=0)
            images = paddle.to_tensor(images)
            if self.config['Architecture']['algorithm'] == "SRN":
                preds = self.model(images, others)
            elif self.config['Architecture']['algorithm'] == "SAR":
                preds = self.model(images, img_metas)
            elif self.config['Architecture']['algorithm'] == "RobustScanner":
                preds = self.model(images, img_metas)
            elif self.config['Architecture']['algorithm'] == "CAN":
                preds = self.model([images, image_mask, label])
            else:
                preds = self.model(images)
            post_result = self.post_process_class(preds)
            info = None
            if isinstance(post_result, dict):
                rec_info = dict()
                for key in post_result:
                    if len(post_result[key][0]) >= 2:
                        rec_info[key] = {
                            "label": post_result[key][0][0],
                            "score": float(post_result[key][0][1]),
                        }
                info = json.dumps(rec_info, ensure_ascii=False)
            elif isinstance(post_result, list) and isinstance(post_result[0],
                                                              int):
                # for RFLearning CNT branch 
                info = str(post_result[0])
            else:
                if len(post_result[0]) >= 2:
                    info = post_result[0][0] + "\t" + str(post_result[0][1])

            # if info is not None:
            #     print(info)
            yield info,bbox[idx]

    def load_checkpoint(self):
        print("开始加载识别模型...")
        start_time = time.time()
        
        # build post process
        self.post_process_class = build_post_process(self.config['PostProcess'],
                                                self.global_config)

        # build model
        if hasattr(self.post_process_class, 'character'):
            char_num = len(getattr(self.post_process_class, 'character'))
            if self.config["Architecture"]["algorithm"] in ["Distillation",
                                                    ]:  # distillation model
                for key in self.config["Architecture"]["Models"]:
                    if self.config["Architecture"]["Models"][key]["Head"][
                            "name"] == 'MultiHead':  # multi head
                        out_channels_list = {}
                        if self.config['PostProcess'][
                                'name'] == 'DistillationSARLabelDecode':
                            char_num = char_num - 2
                        if self.config['PostProcess'][
                                'name'] == 'DistillationNRTRLabelDecode':
                            char_num = char_num - 3
                        out_channels_list['CTCLabelDecode'] = char_num
                        out_channels_list['SARLabelDecode'] = char_num + 2
                        out_channels_list['NRTRLabelDecode'] = char_num + 3
                        self.config['Architecture']['Models'][key]['Head'][
                            'out_channels_list'] = out_channels_list
                    else:
                        self.config["Architecture"]["Models"][key]["Head"][
                            "out_channels"] = char_num
            elif self.config['Architecture']['Head'][
                    'name'] == 'MultiHead':  # multi head
                out_channels_list = {}
                char_num = len(getattr(self.post_process_class, 'character'))
                if self.config['PostProcess']['name'] == 'SARLabelDecode':
                    char_num = char_num - 2
                if self.config['PostProcess']['name'] == 'NRTRLabelDecode':
                    char_num = char_num - 3
                out_channels_list['CTCLabelDecode'] = char_num
                out_channels_list['SARLabelDecode'] = char_num + 2
                out_channels_list['NRTRLabelDecode'] = char_num + 3
                self.config['Architecture']['Head'][
                    'out_channels_list'] = out_channels_list
            else:  # base rec model
                self.config["Architecture"]["Head"]["out_channels"] = char_num
        self.model = build_model(self.config['Architecture'])

        load_model(self.config, self.model)
        # print(self.model)

        self.transforms = []
        for op in self.config['Eval']['dataset']['transforms']:
            op_name = list(op)[0]
            if 'Label' in op_name:
                continue
            elif op_name in ['RecResizeImg']:
                op[op_name]['infer_mode'] = True
            elif op_name == 'KeepKeys':
                if self.config['Architecture']['algorithm'] == "SRN":
                    op[op_name]['keep_keys'] = [
                        'image', 'encoder_word_pos', 'gsrm_word_pos',
                        'gsrm_slf_attn_bias1', 'gsrm_slf_attn_bias2'
                    ]
                elif self.config['Architecture']['algorithm'] == "SAR":
                    op[op_name]['keep_keys'] = ['image', 'valid_ratio']
                elif self.config['Architecture']['algorithm'] == "RobustScanner":
                    op[op_name][
                        'keep_keys'] = ['image', 'valid_ratio', 'word_positons']
                else:
                    op[op_name]['keep_keys'] = ['image']
            self.transforms.append(op)
        self.global_config['infer_mode'] = True
        self.ops = create_operators(self.transforms, self.global_config)
        self.model.eval()
        
        end_time = time.time()
        print(f"识别模型加载完成，耗时: {end_time - start_time:.2f}秒")
    
    def predict(self, img_list):
        print(f"开始文本识别，处理图像数量: {len(img_list)}")
        start_time = time.time()
        
        for idx, img_data in enumerate(img_list):   #get_image_file_list(img_path):
            try:
                _, encoded_image = cv2.imencode(".jpg", img_data)
            except:
                # print(len(img_data))
                # print(img_data)
                continue
            img = encoded_image.tobytes() 
            data = {'image': img}
            batch = transform(data, self.ops)
            if self.config['Architecture']['algorithm'] == "SRN":
                encoder_word_pos_list = np.expand_dims(batch[1], axis=0)
                gsrm_word_pos_list = np.expand_dims(batch[2], axis=0)
                gsrm_slf_attn_bias1_list = np.expand_dims(batch[3], axis=0)
                gsrm_slf_attn_bias2_list = np.expand_dims(batch[4], axis=0)

                others = [
                    paddle.to_tensor(encoder_word_pos_list),
                    paddle.to_tensor(gsrm_word_pos_list),
                    paddle.to_tensor(gsrm_slf_attn_bias1_list),
                    paddle.to_tensor(gsrm_slf_attn_bias2_list)
                ]
            if self.config['Architecture']['algorithm'] == "SAR":
                valid_ratio = np.expand_dims(batch[-1], axis=0)
                img_metas = [paddle.to_tensor(valid_ratio)]
            if self.config['Architecture']['algorithm'] == "RobustScanner":
                valid_ratio = np.expand_dims(batch[1], axis=0)
                word_positons = np.expand_dims(batch[2], axis=0)
                img_metas = [
                    paddle.to_tensor(valid_ratio),
                    paddle.to_tensor(word_positons),
                ]
            if self.config['Architecture']['algorithm'] == "CAN":
                image_mask = paddle.ones(
                    (np.expand_dims(
                        batch[0], axis=0).shape), dtype='float32')
                label = paddle.ones((1, 36), dtype='int64')
            images = np.expand_dims(batch[0], axis=0)
            images = paddle.to_tensor(images)
            if self.config['Architecture']['algorithm'] == "SRN":
                preds = self.model(images, others)
            elif self.config['Architecture']['algorithm'] == "SAR":
                preds = self.model(images, img_metas)
            elif self.config['Architecture']['algorithm'] == "RobustScanner":
                preds = self.model(images, img_metas)
            elif self.config['Architecture']['algorithm'] == "CAN":
                preds = self.model([images, image_mask, label])
            else:
                preds = self.model(images)
            post_result = self.post_process_class(preds)
            info = None
            if isinstance(post_result, dict):
                rec_info = dict()
                for key in post_result:
                    if len(post_result[key][0]) >= 2:
                        rec_info[key] = {
                            "label": post_result[key][0][0],
                            "score": float(post_result[key][0][1]),
                        }
                info = json.dumps(rec_info, ensure_ascii=False)
            elif isinstance(post_result, list) and isinstance(post_result[0],
                                                              int):
                # for RFLearning CNT branch 
                info = str(post_result[0])
            else:
                if len(post_result[0]) >= 2:
                    info = post_result[0][0] + "\t" + str(post_result[0][1]) +"\t" + str(idx)

            # if info is not None:
            #     print(info)
            yield info
        
        end_time = time.time()
        print(f"文本识别完成，耗时: {end_time - start_time:.2f}秒")
        

class OCR_process(object):
    def __init__(self, config_dict):
        print("开始初始化OCR系统...")
        total_start_time = time.time()
        
        # 文本检测
        self.ocr_det = Detection(config_dict["ocr_det_config"])
        self.ocr_det.load_checkpoint()     
        
        self.ocr_rec = OCR_rec(config_dict["ocr_rec_config"])
        self.ocr_rec.load_checkpoint() 
        self.debug_show = True
        
        total_end_time = time.time()
        print(f"OCR系统初始化完成，总耗时: {total_end_time - total_start_time:.2f}秒")

    def sort_boxes(self, boxes):
    # 定义排序规则的函数
        def box_sort_key(box):
            return (box[0][1], box[0][0])  # 先按照y，再按照x
        sorted_boxes = sorted(boxes, key=box_sort_key)
        return sorted_boxes
    
    def clearbox(self, boxes):
        newbox = []
        for box in boxes:
            if len(box)==0:
                continue
            for i in box:
                newbox.append(i.tolist())
        return newbox
    
    def rectify_crop(self, img, info):
        h, w = img.shape[:2]
        left_top, right_top, right_down, left_down = info['ori_pt']
        if info['is_vertical']:
            crop_h = info['bbox_long']
            crop_w = info['bbox_short']
        else:
            crop_h = info['bbox_short']
            crop_w = info['bbox_long']

        new_ld = left_down
        new_lt = [new_ld[0], new_ld[1] - crop_h]
        new_rt = [new_ld[0] + crop_w, new_ld[1] - crop_h]
        new_rd = [new_ld[0] + crop_w, new_ld[1]]

    
        pts1 = np.array([left_top, right_top, right_down, left_down], dtype=np.float32)
        pts2 = np.array([new_lt, new_rt, new_rd, new_ld], dtype=np.float32)

        M = cv2.getPerspectiveTransform(pts1, pts2)

        dst = cv2.warpPerspective(img, M, (w, h))

        new_crop = dst[max(new_lt[1] - 10, 0):min(new_ld[1] + 10, h), max(new_lt[0] - 10, 0):min(new_rt[0] + 10, w)]

        if info['is_vertical']:
            new_crop = cv2.rotate(new_crop, cv2.ROTATE_90_COUNTERCLOCKWISE)
        # import time
        # cv2.imwrite(f'/home/zhenjue3/xcy_temp_work/gxg/door_cemian_ocr/gxg_ocr/test/test_result/{time.time()}.jpg', new_crop)
        return new_crop
    def distance(self, point1, point2):
        point1 = np.array(point1)
        point2 = np.array(point2)
        return np.linalg.norm(point2 - point1)
    def get_bbox_info(self, box):
        info_dict = {}
        if len(box) > 3:
            distances = [
                self.distance(box[0], box[1]),
                self.distance(box[1], box[2]),
                self.distance(box[2], box[3]),
                self.distance(box[3], box[0])
            ]

            short_side = int(min(distances))
            long_side = int(max(distances))
            
            sorted_by_y = sorted(box, key=lambda x: x[1], reverse=True)
            sorted_lst_down = sorted(sorted_by_y[:2], key=lambda m:m[0])
            sorted_lst_top = sorted(sorted_by_y[2:], key=lambda m:m[0])

            left_down = sorted_lst_down[0]
            right_down = sorted_lst_down[1]
            left_top = sorted_lst_top[0]
            right_top = sorted_lst_top[1]

            ori_pt = [left_top, right_top, right_down, left_down]

            down_diff = right_down[0] - left_down[0]

            if abs(down_diff - short_side) < 2:
                img_vertical = True
            else:
                img_vertical = False

            info_dict = {
                'bbox_long': long_side,
                'bbox_short':short_side,
                'ori_pt':ori_pt,
                'is_vertical':img_vertical
            }
            # print(info_dict)
        return info_dict

    def process_imgs(self, img_list):
        print("开始图像处理...")
        total_start_time = time.time()
        
        boxes = self.ocr_det.predict(img_list)
        if(len(boxes)==0):
            logger.warning("未检测到文本框")
            return None
        
        rec = []
        img_draw = None
        for i, i_boxes in enumerate(boxes):
            # print(len(i_boxes))
            crop_img_list = []
            sortboxes = self.sort_boxes(i_boxes) 
            for box in sortboxes:
                bbox_info = self.get_bbox_info(box)
                crop_img = self.rectify_crop(img_list[i], bbox_info)
                # cv2.rectangle(img_list[i], (box[0][0], box[0][1]), (box[2][0], box[2][1]), (255, 0, 0), 2)
                # img_draw = img_list[i].copy()
                # cv2.imwrite("res1.png", img_draw)
                crop_img_list.append(crop_img)
            info_stream = self.ocr_rec.predict(crop_img_list)
            # print(len(crop_img_list))
            # for info in info_stream: 
            #     ocr_str = info.split("\t")
            #     rec.append(ocr_str[0])
            img_draw = img_list[i].copy()

            for id, info in enumerate(info_stream): 
                ocr_str = info.split("\t")
                
                if '#' not in ocr_str[0]:
                    cv2.rectangle(img_draw, (sortboxes[id][0][0], sortboxes[id][0][1]), (sortboxes[id][2][0], sortboxes[id][2][1]), (255, 0, 0), 2)
                    cv2.putText(img_draw, ocr_str[0], (sortboxes[id][0][0], sortboxes[id][0][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
                    rec.append(ocr_str[0])
                # print(ocr_str) 
        
        total_end_time = time.time()
        print(f"图像处理完成，总耗时: {total_end_time - total_start_time:.2f}秒")
        print(f"识别结果数量: {len(rec)}")
        return img_draw, rec
    
    # def check_equ(rec):
    def check_calculations(self, calculations):
        for calculation in calculations:
            calculation = calculation.replace('×', '*').replace('÷', '/')
            try:
                left_side, right_side = calculation.split('=')
                # print(round(eval(left_side)))
                if round(eval(left_side)*10000) == round(float(right_side)*10000):
                    print(f"{calculation} is correct.")
                
                else:
                    print(f"{calculation} is incorrect.")
            except Exception as e:
                print(f"Error evaluating {calculation}: {e}")



if __name__ == "__main__":
    print("=== OCR性能测试开始 ===")
    main_start_time = time.time()
    
    config_dict = {
        "ocr_det_config": "model/det_best_model/config.yml",
        "ocr_rec_config": "configs/rec/PP-OCRv4/ch_PP-OCRv4_rec_hgnet.yml"
    }
    my_ocr_process = OCR_process(config_dict)
    
    print("开始处理测试图像...")
    img = cv2.imread("test_image.png")
    img_draw, rec = my_ocr_process.process_imgs([img])
    cv2.imwrite("res1.png", img_draw)
    print(rec)
    
    main_end_time = time.time()
    print(f"=== OCR性能测试结束，总耗时: {main_end_time - main_start_time:.2f}秒 ===")
    
    # rec = ['6×90=540', '40×90=3600', '360×(2+3)=720', '80×40=3200', '320×2=640', '50×60=3000', '80×20=1600', '40×20=800', '90×20=1800', '30×30=900', '7×70=490', '6×10=60', '5×30=150', '15×30=450', '90×70=6300', '70×21=1470', '40×80=3200', '60×60=3600', '9×70=630', '42×20=840', '8×80=640', '98×0=0', '30×5=150', '7×90=630', '60×40=2400', '4×40=160', '2×90=180', '7×70=490', '4×51=204', '9×80=720']

    # rec = ['10.8-8.4=2.4']
    # my_ocr_process.check_calculations(rec)
    # print(result)