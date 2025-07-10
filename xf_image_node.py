#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from origincar_msg.msg import Sign
from hbm_img_msgs.msg import HbmMsg1080P  # ��������Ϣ��������
import base64
import hashlib
import hmac
import json
from urllib.parse import urlparse
import ssl
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
import websocket
import threading
import _thread as thread
import numpy as np
import cv2

class Event:
    def __init__(self):
        self._event = threading.Event()
        
    def set(self):
        self._event.set()
        
    def wait(self, timeout=None):
        return self._event.wait(timeout)

class ImageUnderstandingServer(Node):
    def __init__(self):
        super().__init__('image_understanding_server')
        
        # ��������
        self.declare_parameter('appid', '2f6a6aa9')
        self.declare_parameter('api_key', '255b0cfda6905b488c67776a057c931b')
        self.declare_parameter('api_secret', 'MGNhZmYxOGUwMzk5OTY3MTc2NjZhMGVl')
        
        # ����������
        self.sign_sub = self.create_subscription(
            Sign,
            '/sign_switch',
            self.sign_callback,
            10)
        
        # ����ͼ����
        self.image_sub = self.create_subscription(
            HbmMsg1080P,
            '/hbmem_img',
            self.image_callback,
            10)
        
        self.get_logger().info("ͼ�����������������ȴ�sign_data=10�ź�...")
        self.processing_lock = threading.Lock()  # ��ֹ�ظ�����
        self.is_processing = False  # ����״̬��־
        self.latest_image_msg = None  # �洢���µ�ͼ����Ϣ
        self.image_lock = threading.Lock()  # ����ͼ�����ݵ���

    def image_callback(self, msg):
        """�洢���µ�ͼ����Ϣ"""
        with self.image_lock:
            self.latest_image_msg = msg
            # self.get_logger().info(f"�յ���ͼ��: {msg.width}x{msg.height}, ͨ����: {msg.channels}")

    def sign_callback(self, msg):
        """�����յ�sign_data=10ʱ����ͼ�����"""
        if msg.sign_data == 10 and not self.is_processing:
            self.get_logger().info("�յ�sign_data=10�źţ���ʼ����ͼ��...")
            
            # ���ô���״̬��־
            with self.processing_lock:
                if self.is_processing:  # ˫�ؼ������
                    return
                self.is_processing = True
            
            try:
                # �ڵ������߳��д���ͼ��
                threading.Thread(target=self.process_latest_image).start()
            except Exception as e:
                self.get_logger().error(f"�����߳�����ʧ��: {str(e)}")
                self.is_processing = False

    def process_latest_image(self):
        """��������ͼ��ĺ����߼�"""
        try:
            # ��ȡ���µ�ͼ����Ϣ
            with self.image_lock:
                if self.latest_image_msg is None:
                    self.get_logger().error("û�п��õ�ͼ������")
                    return
                    
                image_msg = self.latest_image_msg
                self.get_logger().info(f"����ͼ��: {image_msg.width}x{image_msg.height}, ͨ����: {image_msg.channels}")
            
            # ��ROSͼ����Ϣת��ΪOpenCVͼ��
            img_np = np.frombuffer(image_msg.data, dtype=np.uint8).reshape(
                (image_msg.height, image_msg.width, image_msg.channels))
            
            # ��BGRת��ΪRGB�����ͼ����BGR��ʽ��
            if image_msg.channels == 3:
                img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            else:
                img_rgb = img_np
            
            # ��ͼ�����ΪJPEG��ʽ
            success, jpeg_data = cv2.imencode('.jpg', img_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            
            if not success:
                self.get_logger().error("ͼ�����ʧ��")
                return
                
            jpeg_bytes = jpeg_data.tobytes()
            self.get_logger().info(f"ͼ�����ɹ�, ��С: {len(jpeg_bytes)} �ֽ�")
            
            # ׼������
            question = [
                {
                    "role": "user", 
                    "content": base64.b64encode(jpeg_bytes).decode('utf-8'), 
                    "content_type": "image"
                }
            ]
            
            # ����ı�ָ��
            self.get_logger().info("�Զ���������: ����ͼƬ�����Ƶ�����")
            question = self.checklen(self.getText("user", "����ͼƬ�����Ƶ�����", question))
            
            # ��ȡ����
            appid = self.get_parameter('appid').get_parameter_value().string_value
            api_key = self.get_parameter('api_key').get_parameter_value().string_value
            api_secret = self.get_parameter('api_secret').get_parameter_value().string_value
            
            # ��ȡͼ������
            client = XFImageClient(appid, api_key, api_secret, self.get_logger())
            raw_description = client.get_image_description(question)
            
            # ������������
            cleaned_description = self.clean_description(raw_description)
            
            self.get_logger().info(f"ͼ���������ɳɹ�: {cleaned_description}")
            
        except Exception as e:
            self.get_logger().error(f"ͼ����ʧ��: {str(e)}")
        finally:
            # ���ô���״̬��־
            with self.processing_lock:
                self.is_processing = False

    def clean_description(self, description):
        """
        ���������ı����Ƴ�����Ҫ�ķ��ź͸�ʽ���
        """
        # �������Ϊ�գ�ֱ�ӷ���
        if not description:
            return description
        
        # �Ƴ��б��ǣ��� \n1. \n2. �ȣ�
        import re
        description = re.sub(r'\n\d+\.\s*', ' ', description)  # �Ƴ����ֱ��
        
        # �Ƴ���Ŀ���ź�����
        description = description.replace('\n   - ', ' ')
        description = description.replace('\n- ', ' ')
        description = description.replace('   - ', ' ')
        
        # �Ƴ�����Ļ��з�
        description = description.replace('\n', ' ')
        
        # �ϲ�����Ŀո�
        description = re.sub(r'\s+', ' ', description)
        # ȷ���Ծ�Ž�β
        if not description.endswith('��') and not description.endswith('.') and not description.endswith('��'):
            description += '��'
        
        return description.strip()
    
    def getText(self, role, content, text_list):
        """�����Ϣ���Ի��б�"""
        jsoncon = {}
        jsoncon["role"] = role
        jsoncon["content"] = content
        text_list.append(jsoncon)
        return text_list
    
    def getlength(self, text):
        """����Ի�����"""
        length = 0
        for content in text:
            temp = content["content"]
            leng = len(temp)
            length += leng
        return length
    
    def checklen(self, text):
        """��鲢���ƶԻ�����"""
        while (self.getlength(text[1:]) > 8000):
            del text[1]
        return text


class XFImageClient:
    def __init__(self, appid, api_key, api_secret, logger=None):
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.url = "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image"
        self.answer = ""
        self.completion_event = None
        self.logger = logger
        
    def log(self, message):
        if self.logger:
            self.logger.info(message)
        else:
            print(message)

    def get_image_description(self, question):
        # ��ȡ����
        self.completion_event = Event()
        self.answer = ""
        
        ws_param = Ws_Param(self.appid, self.api_key, self.api_secret, self.url)
        ws_url = ws_param.create_url()
        self.log(f"����Ѷ��API: {ws_url}")
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        self.ws.appid = self.appid
        self.ws.question = question
        
        # ����WebSocket
        self.log("����WebSocket����...")
        self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        
        # �ȴ������ʱ
        if not self.completion_event.wait(timeout=30):  # 30�볬ʱ
            self.log("API���ó�ʱ")
            return "API���ó�ʱ��������"
        
        return self.answer

    def on_message(self, ws, message):
        try:
            # ��¼ԭʼ��Ӧ
            self.log(f"�յ�ԭʼ��Ӧ: {message[:500]}...")
            
            data = json.loads(message)
            code = data['header']['code']
            
            if code != 0:
                error_msg = f'API����: {code}, {data["header"]["message"]}'
                self.log(error_msg)
                ws.close()
            else:
                choices = data["payload"]["choices"]
                status = choices["status"]
                content = choices["text"][0]["content"]
                
                # ��¼������Ϣ
                self.log(f"״̬: {status}, ����: {content}")
                
                self.answer += content
                if status == 2:
                    self.log(f"������������: '{self.answer}'")
                    ws.close()
        except Exception as e:
            self.log(f"������Ϣʧ��: {str(e)}")
        finally:
            self.completion_event.set()

    def on_error(self, ws, error):
        self.log(f"WebSocket����: {error}")
        self.completion_event.set()

    def on_close(self, ws, close_status_code, close_msg):
        self.log(f"���ӹر�: {close_status_code} - {close_msg}")
        self.completion_event.set()

    def on_open(self, ws):
        self.log("WebSocket�����ѽ�������������...")
        # ʹ�� thread ģ���������߳�
        thread.start_new_thread(self.run, (ws,))
    
    def run(self, ws, *args):
        self.log("������������...")
        data = json.dumps(self.gen_params(appid=ws.appid, question=ws.question))
        ws.send(data)

    def gen_params(self, appid, question):
        return {
            "header": {"app_id": appid},
            "parameter": {
                "chat": {
                    "domain": "imagev3",
                    "temperature": 0.5,
                    "top_k": 4,
                    "max_tokens": 2028,
                    "auditing": "default"
                }
            },
            "payload": {
                "message": {
                    "text": question
                }
            }
        }


class Ws_Param:
    def __init__(self, APPID, APIKey, APISecret, imageunderstanding_url):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.host = urlparse(imageunderstanding_url).netloc
        self.path = urlparse(imageunderstanding_url).path
        self.ImageUnderstanding_url = imageunderstanding_url

    def create_url(self):
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.path} HTTP/1.1"
        signature_sha = hmac.new(
            self.APISecret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        signature_sha_base64 = base64.b64encode(signature_sha).decode('utf-8')
        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

        v = {"authorization": authorization, "date": date, "host": self.host}
        return self.ImageUnderstanding_url + '?' + urlencode(v)

def main(args=None):
    rclpy.init(args=args)
    server = ImageUnderstandingServer()
    rclpy.spin(server)
    server.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()