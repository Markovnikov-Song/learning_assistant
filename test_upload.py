"""
上传功能测试脚本
用于诊断文件上传过程中的问题
"""

import sys
import os
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# 设置必要的环境变量（用于本地测试）
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_BASE_URL", "https://api.example.com")
os.environ.setdefault("DATA_DIR", str(Path(__file__).parent / "data"))

from backend.app.db import SessionLocal, init_db
from backend.app import models
from backend.app.services.ingest import save_upload
from backend.app.services.chunking import split_pages
from backend.app.services.text_extract import extract_text_with_metadata
from backend.app.services.chunking import _token_len


def test_chunking(file_path: Path):
    """测试chunking是否会产生超过512 tokens的块"""
    print(f"\n{'='*60}")
    print(f"测试文件: {file_path.name}")
    print(f"{'='*60}")
    
    try:
        # 提取文本
        print(f"\n1. 提取文本...")
        pages = extract_text_with_metadata(file_path)
        print(f"   成功提取 {len(pages)} 页")
        
        # 分割成chunks
        print(f"\n2. 分割文本块...")
        chunks = split_pages(pages)
        print(f"   生成 {len(chunks)} 个文本块")
        
        # 检查每个chunk的token数量
        print(f"\n3. 检查token数量...")
        max_tokens = 0
        problematic_chunks = 0
        
        for i, chunk in enumerate(chunks):
            token_count = _token_len(chunk.text)
            if token_count > max_tokens:
                max_tokens = token_count
            
            if token_count > 512:
                problematic_chunks += 1
                print(f"   ⚠️  Chunk {i}: {token_count} tokens (超过512!)")
                print(f"      文本预览: {chunk.text[:100]}...")
            elif i < 5:  # 只显示前5个正常chunk
                print(f"   ✓ Chunk {i}: {token_count} tokens")
        
        print(f"\n4. 统计结果:")
        print(f"   总chunk数: {len(chunks)}")
        print(f"   最大token数: {max_tokens}")
        print(f"   超过512的chunk数: {problematic_chunks}")
        
        if problematic_chunks > 0:
            print(f"\n   ❌ 发现 {problematic_chunks} 个超过512 tokens的chunk!")
            return False
        else:
            print(f"\n   ✅ 所有chunk都在512 tokens以内")
            return True
            
    except Exception as e:
        print(f"\n   ❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_upload(file_path: Path, subject_id: str):
    """测试完整的上传流程"""
    print(f"\n{'='*60}")
    print(f"测试完整上传流程")
    print(f"{'='*60}")
    
    try:
        with SessionLocal() as db:
            # 检查学科是否存在
            subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
            if not subject:
                print(f"\n   ❌ 学科 {subject_id} 不存在")
                return False
            
            print(f"\n   学科: {subject.name}")
            print(f"   文件: {file_path.name}")
            print(f"   文件大小: {file_path.stat().st_size / 1024 / 1024:.2f} MB")
            
            # 执行上传
            print(f"\n   开始上传...")
            doc = save_upload(
                subject_id=subject_id,
                upload_path=file_path,
                original_name=file_path.name,
                mime_type="application/pdf",
                db=db,
            )
            
            print(f"\n   上传结果:")
            print(f"   状态: {doc.status}")
            print(f"   文档ID: {doc.id}")
            
            if doc.error:
                print(f"   错误: {doc.error}")
                return False
            
            if doc.status == "ready":
                print(f"\n   ✅ 上库成功!")
                
                # 检查生成的chunks
                chunks = db.query(models.Chunk).filter(
                    models.Chunk.document_id == doc.id
                ).all()
                print(f"   生成chunks数: {len(chunks)}")
                
                # 检查每个chunk的token数
                max_tokens = 0
                for chunk in chunks:
                    token_count = _token_len(chunk.text)
                    if token_count > max_tokens:
                        max_tokens = token_count
                
                print(f"   最大token数: {max_tokens}")
                return True
            else:
                print(f"\n   ❌ 上库失败")
                return False
                
    except Exception as e:
        print(f"\n   ❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    # 初始化数据库
    init_db()
    
    # 获取测试文件路径
    data_dir = Path(__file__).parent / "data"
    test_files = list(data_dir.glob("*.pdf")) + list(data_dir.glob("*.txt")) + list(data_dir.glob("*.md"))
    
    if not test_files:
        print(f"\n❌ 在 {data_dir} 目录下没有找到测试文件")
        print(f"请将测试文件放到 data 目录下（支持 .pdf, .txt, .md 格式）")
        return
    
    print(f"\n找到 {len(test_files)} 个测试文件:")
    for i, f in enumerate(test_files, 1):
        print(f"   {i}. {f.name}")
    
    # 获取或创建测试学科
    with SessionLocal() as db:
        test_subject = db.query(models.Subject).filter(models.Subject.name == "测试学科").first()
        if not test_subject:
            test_subject = models.Subject(
                name="测试学科",
                category="理科",
                description="用于测试上传功能"
            )
            db.add(test_subject)
            db.commit()
            db.refresh(test_subject)
            print(f"\n✅ 创建测试学科: {test_subject.name} (ID: {test_subject.id})")
        else:
            print(f"\n✅ 使用现有测试学科: {test_subject.name} (ID: {test_subject.id})")
    
    # 测试每个文件
    results = {}
    for test_file in test_files:
        # 测试chunking
        chunking_ok = test_chunking(test_file)
        
        # 测试完整上传
        upload_ok = test_upload(test_file, test_subject.id)
        
        results[test_file.name] = {
            "chunking": chunking_ok,
            "upload": upload_ok
        }
    
    # 打印总结
    print(f"\n{'='*60}")
    print(f"测试总结")
    print(f"{'='*60}")
    for filename, result in results.items():
        status = "✅ 通过" if result["chunking"] and result["upload"] else "❌ 失败"
        print(f"   {filename}: {status}")
        if not result["chunking"]:
            print(f"      - Chunking测试失败")
        if not result["upload"]:
            print(f"      - 上传测试失败")


if __name__ == "__main__":
    main()
