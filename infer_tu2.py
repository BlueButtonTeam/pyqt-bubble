from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np

import os
import sys
import json
# from  numba import cuda
import psutil
__dir__ = os.path.dirname(os.path.abspath(__file__))
sys.path.append(__dir__)
sys.path.insert(0, os.path.abspath(os.path.join(__dir__, '..')))

os.environ["FLAGS_allocator_strategy"] = 'auto_growth'
os.environ["CUDA_VISIBLE_DEVICES"]="0"
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
import time
from PIL import Image, ImageDraw, ImageFont
# try:
#     from OCR_TOOL import ocr as ocr_check
# except:
#     from .OCR_TOOL import ocr as ocr_check
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
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
        img_box = []
        for img_data in img_list:
            h,w = img_data.shape[:2]
            _, encoded_image = cv2.imencode(".jpg", img_data)
            img = encoded_image.tobytes()
            box = self._predict2box(img)
            img_box.append(box)

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
    
    def predict(self, img_list):
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
        

class OCR_process(object):
    def __init__(self, config_dict):
        # 文本检测
        self.ocr_det = Detection(config_dict["ocr_det_config"])
        self.ocr_det.load_checkpoint()     
        
        self.ocr_rec = OCR_rec(config_dict["ocr_rec_config"])
        self.ocr_rec.load_checkpoint() 
        self.debug_show = True

        # 添加MKLDNN加速相关属性
        self.enable_mkldnn = False
        self.mkldnn_cache_capacity = 10
        self.cpu_threads = 8
        
        # 应用配置
        self._apply_config_to_models()
        
    def _apply_config_to_models(self):
        """将配置应用到模型中"""
        try:
            # 将MKLDNN配置应用到detection模型
            if hasattr(self.ocr_det, 'config') and 'Global' in self.ocr_det.config:
                self.ocr_det.config['Global']['enable_mkldnn'] = self.enable_mkldnn
                self.ocr_det.config['Global']['mkldnn_cache_capacity'] = self.mkldnn_cache_capacity
                self.ocr_det.config['Global']['cpu_threads'] = self.cpu_threads
                print(f"✓ 文本检测模型已设置线程数: {self.cpu_threads}")
                
            # 将MKLDNN配置应用到recognition模型
            if hasattr(self.ocr_rec, 'config') and 'Global' in self.ocr_rec.config:
                self.ocr_rec.config['Global']['enable_mkldnn'] = self.enable_mkldnn
                self.ocr_rec.config['Global']['mkldnn_cache_capacity'] = self.mkldnn_cache_capacity
                self.ocr_rec.config['Global']['cpu_threads'] = self.cpu_threads
                print(f"✓ 文本识别模型已设置线程数: {self.cpu_threads}")

            # 显示总体优化设置
            if self.enable_mkldnn:
                print(f"✅ MKLDNN加速已启用，缓存容量: {self.mkldnn_cache_capacity}，线程数: {self.cpu_threads}")
        except Exception as e:
            print(f"⚠️ 应用MKLDNN配置时出错: {str(e)}")

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
            new_crop = cv2.rotate(new_crop, cv2.ROTATE_90_CLOCKWISE)
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
        boxes = self.ocr_det.predict(img_list)
        if(len(boxes)==0):
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
            pil_image = Image.fromarray(cv2.cvtColor(img_draw, cv2.COLOR_BGR2RGB))

            # 创建一个绘制对象
            draw = ImageDraw.Draw(pil_image)
            for id, info in enumerate(info_stream): 
                ocr_str = info.split("\t")
                
                if '#' not in ocr_str[0]:
                    cv2.rectangle(img_draw, (sortboxes[id][0][0], sortboxes[id][0][1]), (sortboxes[id][2][0], sortboxes[id][2][1]), (255, 0, 0), 2)
                    cv2.putText(img_draw, ocr_str[0], (sortboxes[id][0][0], sortboxes[id][0][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
                    draw.text((sortboxes[id][0][0], sortboxes[id][0][1] - 10), ocr_str[0], fill=(255, 0, 0))
                    rec.append(ocr_str[0])
            cv2_text_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                # print(ocr_str) 
        return img_draw, rec, cv2_text_image
    


if __name__ == "__main__":
    import time
    from datetime import datetime

    # 记录开始时间
    start_time = time.time()
    start_datetime = datetime.now()
    print(f"\n📋 OCR识别开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

    config_dict = {
        "ocr_det_config": "model/det_best_model/config.yml",
        "ocr_rec_config": "configs/rec/PP-OCRv4/ch_PP-OCRv4_rec_hgnet.yml"
    }

    print("🔧 正在初始化OCR模型...")
    init_start = time.time()
    my_ocr_process = OCR_process(config_dict)
    
    # 启用MKLDNN加速
    try:
        my_ocr_process.enable_mkldnn = True
        my_ocr_process.mkldnn_cache_capacity = 10
        my_ocr_process.cpu_threads = 8
        my_ocr_process._apply_config_to_models()
        print("✅ 已启用MKLDNN加速")
    except Exception as e:
        print(f"⚠️ 无法启用MKLDNN加速: {e}")
    
    init_time = time.time() - init_start
    print(f"✅ 模型初始化完成，耗时: {init_time:.2f}秒")

    print("📖 正在读取图像...")
    img_start = time.time()
    img = cv2.imread("test_image.png")
    if img is None:
        print("❌ 无法读取图像文件: test_image.png")
        exit(1)
    img_time = time.time() - img_start
    print(f"🖼️ 图像读取成功，尺寸: {img.shape}，耗时: {img_time:.2f}秒")

    print("🔍 开始OCR识别...")
    ocr_start = time.time()
    img_draw, rec, cv2_text_image = my_ocr_process.process_imgs([img])
    ocr_time = time.time() - ocr_start
    print(f"✅ OCR识别完成，耗时: {ocr_time:.2f}秒")

    print("💾 正在保存结果...")
    save_start = time.time()
    cv2.imwrite("res1.png", img_draw)
    cv2.imwrite("res2.png", cv2_text_image)
    save_time = time.time() - save_start
    print(f"📁 结果已保存: res1.png, res2.png，耗时: {save_time:.2f}秒")

    # 计算总耗时
    total_time = time.time() - start_time
    end_datetime = datetime.now()

    print(f"\n📊 识别结果 (共{len(rec)}个文本):")
    print(rec)

    print("\n⏱️ 时间统计:")
    print(f"  模型初始化: {init_time:.2f}秒 ({(init_time/total_time*100):.1f}%)")
    print(f"  图像读取: {img_time:.2f}秒 ({(img_time/total_time*100):.1f}%)")
    print(f"  OCR处理: {ocr_time:.2f}秒 ({(ocr_time/total_time*100):.1f}%)")
    print(f"  结果保存: {save_time:.2f}秒 ({(save_time/total_time*100):.1f}%)")
    print(f"  总耗时: {total_time:.2f}秒")
    print(f"📋 OCR识别结束时间: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    # rec = ['6×90=540', '40×90=3600', '360×(2+3)=720', '80×40=3200', '320×2=640', '50×60=3000', '80×20=1600', '40×20=800', '90×20=1800', '30×30=900', '7×70=490', '6×10=60', '5×30=150', '15×30=450', '90×70=6300', '70×21=1470', '40×80=3200', '60×60=3600', '9×70=630', '42×20=840', '8×80=640', '98×0=0', '30×5=150', '7×90=630', '60×40=2400', '4×40=160', '2×90=180', '7×70=490', '4×51=204', '9×80=720']

    # rec = ['10.8-8.4=2.4']
    # my_ocr_process.check_calculations(rec)
    # print(result)