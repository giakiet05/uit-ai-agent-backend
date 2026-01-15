"""
LlamaParse for PDF parsing.

Parse PDFs (text or scanned) to markdown using LlamaCloud API.
"""

from pathlib import Path
from typing import Optional
from llama_cloud_services import LlamaParse

from config import settings
from utils.logger import logger


class LlamaParseOCR:
    """Parse PDFs (text or scanned) using LlamaParse."""

    def __init__(
        self,
        tier: str = "agentic_plus",
    ):
        """
        Initialize LlamaParseOCR.

        Args:
            tier: Parsing tier (fast, cost_effective, agentic, agentic_plus)

        Raises:
            ValueError: If API key not found
        """
        api_key = settings.credentials.LLAMA_CLOUD_API_KEY

        if not api_key:
            raise ValueError("LLAMA_CLOUD_API_KEY not found. Please set in .env file.")

        logger.info(f"[LLAMAPARSE] Initializing with tier: {tier}")

        # Prompt for parsing Vietnamese university regulation documents
        system_prompt = """LOẠI TÀI LIỆU:
Đây là các văn bản quy định chính thức của Trường Đại học Công nghệ Thông tin (UIT), Việt Nam.

CẤU TRÚC PHÂN CẤP:

Các văn bản quy định của Việt Nam tuân theo cấu trúc phân cấp: Chương -> Điều.

Áp dụng markdown heading như sau:
- Chương: Sử dụng # (H1)
- Điều: Sử dụng ## (H2)

VÍ DỤ - Cấu trúc heading đúng:

# Chương 1. NHỮNG QUY ĐỊNH CHUNG

## Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng
Quy định này quy định những điều chung nhất về đào tạo Đại học chính quy CTTN của Trường ĐHCNTT thuộc ĐHQG-HCM và nằm trong khuôn khổ quy chế đào tạo theo học chế tín chỉ cho hệ đại học chính quy của Trường ĐHCNTT.

## Điều 8. Phương thức xét tuyển đầu vào
Căn cứ vào số lượng đăng ký xét tuyển hàng năm, BĐH quyết định chỉ tiêu tuyển vào lớp tài năng và trình BGH phê duyệt.

Việc xét tuyển đầu vào được áp dụng 1 trong 2 phương án sau:

1. Tuyển từ năm 1 - theo kết quả đầu vào tuyển sinh
Chỉ tiêu tuyển sinh tối đa là 30 sinh viên/chương trình, nằm trong tổng chỉ tiêu toàn trường và đảm bảo điều kiện không quá 20% chỉ tiêu của ngành tương ứng.

Đối tượng tuyển sinh là các sinh viên tự nguyện tham gia vào CTTN và đã trúng tuyển vào hệ chính quy của Trường Đại học Công nghệ Thông tin.
 
2. Tuyển sinh viên năm trên
Tuyển đầu vào lớp CTTN sau học kỳ thứ nhất nhưng không muộn hơn học kỳ thứ ba. Nếu khoa có tiến hành phân ngành/chuyên ngành thì bắt buộc phải tổ chức tuyển vào lớp CTTN không muộn hơn thời điểm phân ngành này.

MỤC LỤC - KHÔNG THÊM HEADING:

Tài liệu có thể chứa phần Mục lục. Đây là nơi các chương, điều và khoản được liệt kê kèm số trang nhưng KHÔNG có nội dung thực sự của chúng.

Cách nhận biết Mục lục:
- Các Chương/Điều xuất hiện liên tục
- Mỗi dòng kết thúc bằng số trang (như "....... 3" hoặc "....... 5")
- Không có nội dung/đoạn văn thực sự giữa các mục được liệt kê

KHÔNG áp dụng định dạng heading (#, ##) cho các mục trong Mục lục.

VÍ DỤ - Mục lục (không áp dụng heading):

Chương 1. NHỮNG QUY ĐỊNH CHUNG ........................................................................ 3
Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng ........................................................ 3
Điều 2. Giải thích từ ngữ ............................................................................................... 3
Điều 3. Mục tiêu đào tạo ............................................................................................... 3
Chương 2. CƠ CẤU TỔ CHỨC QUẢN LÝ .................................................................... 5
Điều 4. Cơ cấu tổ chức .................................................................................................. 5
Điều 5. Trách nhiệm của Ban Điều hành cấp Trường ................................................... 5

---

NỘI DUNG CẦN LOẠI BỎ KHỎI OUTPUT:

1. Số trang: Loại bỏ các số đứng một mình biểu thị số trang (như "1", "7", "12" xuất hiện riêng lẻ trên một dòng hoặc ở cuối nội dung).

2. Header cố định của văn bản: Các văn bản hành chính Việt Nam thường có header lặp lại trên mỗi trang mà không chứa nội dung có ý nghĩa. Bỏ qua các header này.

Các header này thường chứa:
- Tên trường và tổ chức chủ quản (ví dụ: "Đại học Quốc gia", "Trường Đại học Công nghệ Thông tin", hoặc các tên tổ chức tương tự)
- Mẫu khẩu hiệu quốc gia: "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" theo sau là "Độc lập - Tự do - Hạnh phúc"
- Các yếu tố này có thể xuất hiện với các biến thể nhỏ về định dạng, viết hoa, hoặc xuống dòng

VÍ DỤ - Các header cần bỏ qua:

ĐẠI HỌC QUỐC GIA TP.HCM
TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN

CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Hoặc các biến thể như:

ĐẠI HỌC QUỐC GIA TP.HCM          CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN          Độc lập - Tự do - Hạnh phúc

Đây là các header tiêu chuẩn của văn bản hành chính và cần được loại bỏ bất kể định dạng chính xác hay các biến thể nhỏ về văn bản.
"""

        try:
            self.parser = LlamaParse(
                api_key=api_key,
                tier=tier,
                version="latest",
                output_tables_as_HTML=True,
                max_pages=0,
                precise_bounding_box=True,
                system_prompt_append=system_prompt,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize LlamaParse: {str(e)}") from e

    def parse_pdf(
        self,
        pdf_path: str | Path,
        output_path: Optional[str | Path] = None,
        skip_existing: bool = True,
    ) -> Optional[str]:
        """
        Parse PDF (text or scanned) to markdown.

        Args:
            pdf_path: Path to input PDF file
            output_path: Optional path to save markdown output (default: data/markdown/)
            skip_existing: Skip if markdown file already exists

        Returns:
            Markdown content as string, or None if skipped

        Raises:
            FileNotFoundError: If PDF not found
            RuntimeError: If parsing fails
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {pdf_path}")

        # Determine output path
        if output_path:
            output_path = Path(output_path)
        else:
            doc_id = pdf_path.stem
            output_path = settings.paths.get_markdown_file(doc_id)

        # Skip if already exists
        if skip_existing and output_path.exists():
            logger.info(f"[LLAMAPARSE] Skipping (already exists): {pdf_path.name}")
            return None

        logger.info(f"[LLAMAPARSE] Parsing: {pdf_path.name}")

        try:
            # Parse document
            result = self.parser.parse(str(pdf_path))

            # Extract markdown (full document, not split by page)
            markdown_docs = result.get_markdown_documents(split_by_page=False)

            if not markdown_docs or not markdown_docs[0].text:
                raise RuntimeError(
                    f"LlamaParse returned empty content for: {pdf_path.name}"
                )

            markdown_text = markdown_docs[0].text

            logger.info(f"[LLAMAPARSE] Parsed successfully: {len(markdown_text)} chars")

            # Save to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_text, encoding="utf-8")
            logger.info(f"[LLAMAPARSE] Saved to: {output_path}")

            return markdown_text

        except Exception as e:
            logger.error(f"[LLAMAPARSE] Failed to parse {pdf_path.name}: {str(e)}")
            raise


def main():
    """
    CLI interface for LlamaParse.

    Usage:
        python -m src.llamaparse_ocr <pdf_path> [--output <output_path>]
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse PDF (text or scanned) to markdown using LlamaParse"
    )
    parser.add_argument("pdf_path", help="Path to input PDF file")
    parser.add_argument(
        "--output",
        help="Path to output markdown file (default: data/markdown/)",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Don't skip existing files, re-parse them",
    )

    args = parser.parse_args()

    # Initialize parser
    llama_parser = LlamaParseOCR()

    # Parse PDF
    try:
        llama_parser.parse_pdf(
            pdf_path=args.pdf_path,
            output_path=args.output,
            skip_existing=not args.no_skip,
        )

    except Exception as e:
        logger.error(f"[ERROR] {e}")
        raise


if __name__ == "__main__":
    main()
