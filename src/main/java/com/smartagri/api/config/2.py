import json
import requests
import time
import pandas as pd
from typing import Dict, List, Optional

class StockInfoEnhancer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_stock_basic_info(self, stock_code: str) -> Dict:
        """
        获取股票基本信息
        这里提供了多个数据源的示例，可以根据需要选择使用
        """
        # 清理股票代码
        code = stock_code.replace('.SH', '').replace('.SZ', '')
        
        stock_info = {
            'stock_code': stock_code,
            'current_price': None,
            'market_cap': None,
            'pe_ratio': None,
            'pb_ratio': None,
            'exchange': None,
            'industry': None,
            'total_shares': None,
            'circulating_shares': None,
            'eps': None,
            'bps': None,
            'roe': None,
            'debt_ratio': None,
            'revenue': None,
            'net_profit': None,
            'gross_margin': None,
            'net_margin': None,
            'query_status': 'pending'
        }
        
        try:
            # 方法1: 使用新浪财经API
            sina_info = self._get_sina_stock_info(code)
            if sina_info:
                stock_info.update(sina_info)
                stock_info['query_status'] = 'success'
                return stock_info
            
            # 方法2: 使用腾讯财经API (备用)
            tencent_info = self._get_tencent_stock_info(code, stock_code)
            if tencent_info:
                stock_info.update(tencent_info)
                stock_info['query_status'] = 'success'
                return stock_info
                
            # 方法3: 使用东方财富API (备用)
            eastmoney_info = self._get_eastmoney_stock_info(code, stock_code)
            if eastmoney_info:
                stock_info.update(eastmoney_info)
                stock_info['query_status'] = 'success'
                return stock_info
                
        except Exception as e:
            print(f"查询股票 {stock_code} 信息时出错: {e}")
            stock_info['query_status'] = f'error: {str(e)}'
        
        return stock_info
    
    def _get_sina_stock_info(self, code: str) -> Optional[Dict]:
        """使用新浪财经API获取股票信息"""
        try:
            # 判断市场
            if code.startswith('6'):
                market_code = f'sh{code}'
            else:
                market_code = f'sz{code}'
            
            url = f'https://hq.sinajs.cn/list={market_code}'
            response = self.session.get(url, timeout=10)
            response.encoding = 'gbk'
            
            if response.status_code == 200 and 'hq_str' in response.text:
                data_str = response.text.split('"')[1]
                if data_str:
                    data_list = data_str.split(',')
                    if len(data_list) > 30:
                        return {
                            'current_price': float(data_list[3]) if data_list[3] else None,
                            'opening_price': float(data_list[1]) if data_list[1] else None,
                            'closing_price': float(data_list[2]) if data_list[2] else None,
                            'highest_price': float(data_list[4]) if data_list[4] else None,
                            'lowest_price': float(data_list[5]) if data_list[5] else None,
                            'volume': int(data_list[8]) if data_list[8] else None,
                            'turnover': float(data_list[9]) if data_list[9] else None,
                            'exchange': '上海证券交易所' if code.startswith('6') else '深圳证券交易所',
                            'last_update': data_list[30] if len(data_list) > 30 else None
                        }
        except Exception as e:
            print(f"新浪财经API查询失败: {e}")
        return None
    
    def _get_tencent_stock_info(self, code: str, full_code: str) -> Optional[Dict]:
        """使用腾讯财经API获取股票信息"""
        try:
            # 判断市场
            if code.startswith('6'):
                market_code = f'sh{code}'
            else:
                market_code = f'sz{code}'
            
            url = f'https://qt.gtimg.cn/q={market_code}'
            response = self.session.get(url, timeout=10)
            response.encoding = 'gbk'
            
            if response.status_code == 200:
                data_str = response.text.strip()
                if '~' in data_str:
                    data_list = data_str.split('~')
                    if len(data_list) > 40:
                        return {
                            'current_price': float(data_list[3]) if data_list[3] else None,
                            'opening_price': float(data_list[5]) if data_list[5] else None,
                            'closing_price': float(data_list[4]) if data_list[4] else None,
                            'highest_price': float(data_list[33]) if data_list[33] else None,
                            'lowest_price': float(data_list[34]) if data_list[34] else None,
                            'volume': int(data_list[6]) if data_list[6] else None,
                            'market_cap': float(data_list[45]) if len(data_list) > 45 and data_list[45] else None,
                            'pe_ratio': float(data_list[39]) if len(data_list) > 39 and data_list[39] else None,
                            'pb_ratio': float(data_list[46]) if len(data_list) > 46 and data_list[46] else None,
                            'exchange': '上海证券交易所' if code.startswith('6') else '深圳证券交易所'
                        }
        except Exception as e:
            print(f"腾讯财经API查询失败: {e}")
        return None
    
    def _get_eastmoney_stock_info(self, code: str, full_code: str) -> Optional[Dict]:
        """使用东方财富API获取股票信息"""
        try:
            # 判断市场代码
            if code.startswith('6'):
                secid = f'1.{code}'  # 沪市
            else:
                secid = f'0.{code}'  # 深市
            
            url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f53,f54,f55,f56,f57,f58'
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('rc') == 0 and data.get('data'):
                    stock_data = data['data']
                    return {
                        'current_price': stock_data.get('f43', 0) / 100 if stock_data.get('f43') else None,
                        'highest_price': stock_data.get('f44', 0) / 100 if stock_data.get('f44') else None,
                        'lowest_price': stock_data.get('f45', 0) / 100 if stock_data.get('f45') else None,
                        'opening_price': stock_data.get('f46', 0) / 100 if stock_data.get('f46') else None,
                        'closing_price': stock_data.get('f47', 0) / 100 if stock_data.get('f47') else None,
                        'volume': stock_data.get('f48'),
                        'turnover': stock_data.get('f49'),
                        'market_cap': stock_data.get('f57'),
                        'pe_ratio': stock_data.get('f54'),
                        'pb_ratio': stock_data.get('f55'),
                        'exchange': '上海证券交易所' if code.startswith('6') else '深圳证券交易所'
                    }
        except Exception as e:
            print(f"东方财富API查询失败: {e}")
        return None
    
    def enhance_json_data(self, json_data: Dict) -> Dict:
        """
        增强JSON数据，为每个股票添加详细信息
        """
        enhanced_data = json_data.copy()
        
        if 'output' in enhanced_data:
            for i, item in enumerate(enhanced_data['output']):
                if 'stock_code' in item:
                    stock_code = item['stock_code']
                    print(f"正在查询股票: {item.get('target_name', '')} ({stock_code})")
                    
                    # 获取股票信息
                    stock_info = self.get_stock_basic_info(stock_code)
                    
                    # 添加到原数据中
                    enhanced_data['output'][i]['stock_info'] = stock_info
                    
                    # 添加查询时间戳
                    enhanced_data['output'][i]['query_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 避免请求过于频繁
                    time.sleep(0.5)
        
        return enhanced_data
    
    def process_json_file(self, input_file: str, output_file: str = None):
        """
        处理JSON文件
        """
        try:
            # 读取原始JSON文件
            with open(input_file, 'r', encoding='utf-8') as f:
                original_data = json.load(f)
            
            print(f"已读取原始数据，包含 {len(original_data.get('output', []))} 条记录")
            
            # 增强数据
            enhanced_data = self.enhance_json_data(original_data)
            
            # 确定输出文件名
            if output_file is None:
                output_file = input_file.replace('.json', '_enhanced.json')
            
            # 保存增强后的数据
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(enhanced_data, f, ensure_ascii=False, indent=2)
            
            print(f"增强后的数据已保存到: {output_file}")
            return enhanced_data
            
        except Exception as e:
            print(f"处理文件时出错: {e}")
            return None

def main():
    """主函数"""
    enhancer = StockInfoEnhancer()
    
    # 处理JSON文件
    input_file = "2.json"  # 替换为您的JSON文件路径
    output_file = "enhanced_stock_data.json"  # 输出文件路径
    
    result = enhancer.process_json_file(input_file, output_file)
    
    if result:
        print("数据增强完成！")
        
        # 显示统计信息
        successful_queries = sum(1 for item in result.get('output', []) 
                               if item.get('stock_info', {}).get('query_status') == 'success')
        total_items = len(result.get('output', []))
        
        print(f"总计: {total_items} 只股票")
        print(f"成功查询: {successful_queries} 只股票")
        print(f"查询成功率: {successful_queries/total_items*100:.1f}%")
    else:
        print("数据增强失败！")

if __name__ == "__main__":
    main()