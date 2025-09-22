import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np

def preprocess_image(image_path):
    """
    图像预处理，提高OCR识别率
    """
    # 使用PIL打开图像
    pil_image = Image.open(image_path)
    
    # 转换为RGB模式（如果不是的话）
    if pil_image.mode != 'RGB':
        pil_image = pil_image.convert('RGB')
    
    # 转换为numpy数组供OpenCV处理
    img_array = np.array(pil_image)
    img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    
    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 方法1：简单二值化
    _, thresh1 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    
    # 方法2：自适应阈值
    thresh2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    
    # 方法3：OTSU二值化
    _, thresh3 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 形态学操作去噪
    kernel = np.ones((2,2), np.uint8)
    cleaned = cv2.morphologyEx(thresh3, cv2.MORPH_CLOSE, kernel)
    
    return [
        Image.fromarray(gray),
        Image.fromarray(thresh1),
        Image.fromarray(thresh2), 
        Image.fromarray(thresh3),
        Image.fromarray(cleaned)
    ]

def enhance_image_pil(image_path):
    """
    使用PIL增强图像
    """
    image = Image.open(image_path)
    
    # 转换为RGB
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # 放大图像
    width, height = image.size
    image = image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
    
    # 增强对比度
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    
    # 增强锐度
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.5)
    
    # 转换为灰度
    image = image.convert('L')
    
    # 应用滤镜
    image = image.filter(ImageFilter.MedianFilter())
    
    return image

def extract_text_multiple_methods(image_path):
    """
    使用多种方法尝试提取文字
    """
    results = {}
    
    # 原始图像
    original_image = Image.open(image_path)
    
    # 方法1：直接提取
    try:
        text1 = pytesseract.image_to_string(original_image, lang='chi_sim')
        results['原始图像'] = text1.strip()
    except Exception as e:
        results['原始图像'] = f"错误: {str(e)}"
    
    # 方法2：PIL增强后提取
    try:
        enhanced_image = enhance_image_pil(image_path)
        text2 = pytesseract.image_to_string(enhanced_image, lang='chi_sim')
        results['PIL增强'] = text2.strip()
    except Exception as e:
        results['PIL增强'] = f"错误: {str(e)}"
    
    # 方法3：OpenCV预处理后提取
    try:
        processed_images = preprocess_image(image_path)
        method_names = ['灰度图', '简单二值化', '自适应阈值', 'OTSU二值化', '形态学处理']
        
        for i, processed_img in enumerate(processed_images):
            try:
                text = pytesseract.image_to_string(processed_img, lang='chi_sim')
                results[method_names[i]] = text.strip()
            except Exception as e:
                results[method_names[i]] = f"错误: {str(e)}"
    except Exception as e:
        results['OpenCV预处理'] = f"错误: {str(e)}"
    
    # 方法4：尝试不同的PSM模式
    psm_modes = [6, 7, 8, 11, 13]  # 不同的页面分割模式
    for psm in psm_modes:
        try:
            custom_config = f'--oem 3 --psm {psm}'
            text = pytesseract.image_to_string(original_image, lang='chi_sim', config=custom_config)
            results[f'PSM模式{psm}'] = text.strip()
        except Exception as e:
            results[f'PSM模式{psm}'] = f"错误: {str(e)}"
    
    return results

# 主执行代码
if __name__ == "__main__":
    image_path = "E:/documents/历史/1335年亚洲.png"
    
    print("正在尝试多种方法提取文字...\n")
    
    results = extract_text_multiple_methods(image_path)
    
    # 显示结果
    for method, text in results.items():
        print(f"=== {method} ===")
        if text:
            print(text)
        else:
            print("未提取到文字")
        print("-" * 50)
    
    # 保存预处理后的图像以便查看效果
    try:
        processed_images = preprocess_image(image_path)
        method_names = ['gray', 'thresh1', 'thresh2', 'thresh3', 'cleaned']
        
        base_path = "E:/documents/历史/"
        for i, img in enumerate(processed_images):
            save_path = f"{base_path}processed_{method_names[i]}.png"
            img.save(save_path)
            print(f"已保存预处理图像: {save_path}")
    except Exception as e:
        print(f"保存预处理图像时出错: {str(e)}")

# 额外的故障排除建议
print("\n=== 故障排除建议 ===")
print("1. 确认tesseract已正确安装:")
print("   pip install pytesseract")
print("   并下载tesseract二进制文件")

print("\n2. 确认中文语言包已安装:")
print("   下载chi_sim.traineddata文件")
print("   放置到tesseract的tessdata目录")

print("\n3. 如果仍有问题，可以手动指定tesseract路径:")
print("   pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'")

print("\n4. 检查图像质量:")
print("   - 文字是否清晰")
print("   - 对比度是否足够")
print("   - 分辨率是否足够高")
print("   - 背景是否干净")