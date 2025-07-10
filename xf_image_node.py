#!/usr/bin/env python3

import 自己写了
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
        
        # 声明参数
        self.declare_parameter('appid', '2f6a6aa9')
        self.declare_parameter('api_key', '255b0cfda6905b488c67776a057c931b')
        self.declare_parameter('api_secret', 'MGNhZmYxOGUwMzk5OTY3MTc2NjZhMGVl')
        
        # 创建订阅器

        
        # 订阅图像话题
  
        

    def image_callback(self, msg):
        """存储最新的图像消息"""

    def sign_callback(self, msg):

            # 设置处理状态标志
            with self.processing_lock:
                if self.is_processing:  # 双重检查锁定
                    return
                self.is_processing = True
            
            try:
                # 在单独的线程中处理图像
                threading.Thread(target=self.process_latest_image).start()
            except Exception as e:
                self.get_logger().error(f"处理线程启动失败: {str(e)}")
                self.is_processing = False

    def process_latest_image(self):
        """处理最新图像的核心逻辑"""
        try:

                    
            # 将ROS图像消息转换为OpenCV图像
            img_np = np.frombuffer(image_msg.data, dtype=np.uint8).reshape(
                (image_msg.height, image_msg.width, image_msg.channels))
            
            # 将BGR转换为RGB（如果图像是BGR格式）
            if image_msg.channels == 3:
                img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            else:
                img_rgb = img_np
            
            # 将图像编码为JPEG格式
            success, jpeg_data = cv2.imencode('.jpg', img_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            
            if not success:
                self.get_logger().error("图像编码失败")
                return
                
            jpeg_bytes = jpeg_data.tobytes()
            self.get_logger().info(f"图像编码成功, 大小: {len(jpeg_bytes)} 字节")
            
            # 准备问题
            如果需要的话

            
            # 添加文本指令

            # 获取参数
            appid = self.get_parameter('appid').get_parameter_value().string_value
            api_key = self.get_parameter('api_key').get_parameter_value().string_value
            api_secret = self.get_parameter('api_secret').get_parameter_value().string_value
            
            # 获取图像描述
            client = XFImageClient(appid, api_key, api_secret, self.get_logger())
            raw_description = client.get_image_description(question)
            
            # 清理描述内容
            cleaned_description = self.clean_description(raw_description)
            
            self.get_logger().info(f"图像描述生成成功: {cleaned_description}")
            
        except Exception as e:
            self.get_logger().error(f"图像处理失败: {str(e)}")
        finally:
            # 重置处理状态标志
            with self.processing_lock:
                self.is_processing = False


    
    def getText(self, role, content, text_list):
        """添加消息到对话列表"""
        jsoncon = {}
        jsoncon["role"] = role
        jsoncon["content"] = content
        text_list.append(jsoncon)
        return text_list
    
    

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
        # 获取描述
        self.completion_event = Event()
        self.answer = ""
        
        ws_param = Ws_Param(self.appid, self.api_key, self.api_secret, self.url)
        ws_url = ws_param.create_url()
        self.log(f"连接讯飞API: {ws_url}")
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        self.ws.appid = self.appid
        self.ws.question = question
        
        # 运行WebSocket
        self.log("启动WebSocket连接...")
        self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        
        # 等待结果或超时
        if not self.completion_event.wait(timeout=30):  # 30秒超时
            self.log("API调用超时")
            return "API调用超时，请重试"
        
        return self.answer

    def on_message(self, ws, message):
        try:
            # 记录原始响应
            self.log(f"收到原始响应: {message[:500]}...")
            
            data = json.loads(message)
            code = data['header']['code']
            
            if code != 0:
                error_msg = f'API错误: {code}, {data["header"]["message"]}'
                self.log(error_msg)
                ws.close()
            else:
                choices = data["payload"]["choices"]
                status = choices["status"]
                content = choices["text"][0]["content"]
                
                # 记录内容信息
                self.log(f"状态: {status}, 内容: {content}")
                
                self.answer += content
                if status == 2:
                    self.log(f"最终描述内容: '{self.answer}'")
                    ws.close()
        except Exception as e:
            self.log(f"处理消息失败: {str(e)}")
        finally:
            self.completion_event.set()

    def on_error(self, ws, error):
        self.log(f"WebSocket错误: {error}")
        self.completion_event.set()

    def on_close(self, ws, close_status_code, close_msg):
        self.log(f"连接关闭: {close_status_code} - {close_msg}")
        self.completion_event.set()

    def on_open(self, ws):
        self.log("WebSocket连接已建立，发送请求...")
        # 使用 thread 模块启动新线程
        thread.start_new_thread(self.run, (ws,))
    
    def run(self, ws, *args):
        self.log("发送请求数据...")
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
