from typing import List, Dict, Any
import json

async def main(args: Dict[str, Any]) -> List[str]:
    try:
        # 读取1.js文件
        with open('src/main/java/com/smartagri/api/config/1.js', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 提取所有URL
        urls = []
        for item in data:
            # 提取URL
            doc_results = item.get('data', {}).get('webPages',{}).get('value',{}).get('url', [])
            for doc in doc_results:
                if 'url' in doc:
                    urls.append(doc['url'])
        
        return urls

    except Exception as e:
        print(f"Error: {e}")
        return []

# 测试代码
if __name__ == "__main__":
    import asyncio
    
    # 创建测试参数
    test_args = {
        "params": {
            "input": []  # 这里不需要实际输入，因为我们直接从文件读取
        }
    }
    
    # 运行主函数
    result = asyncio.run(main(test_args))
    
    # 打印结果
    print(f"找到 {len(result)} 个URL:")
    for url in result:
        print(url)
