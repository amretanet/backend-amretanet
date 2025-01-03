from io import BytesIO
from fpdf import FPDF
from PIL import Image
import os
from dotenv import load_dotenv
from urllib.parse import urljoin
from app.modules.generals import GetCurrentDateTime, ThousandSeparator, DateIDFormatter

load_dotenv()

PROJECT_PATH = os.getenv("PROJECT_PATH")


def paymentStatusFormatter(status: str):
    if status == "PAID":
        return "SUDAH DIBAYAR"
    elif status == "PENDING":
        return "MENUNGGU KONFIRMASI"
    elif status == "UNPAID":
        return "BELUM DIBAYAR"
    elif status == "CONFIRM":
        return "MENUNGGU KONFIRMASI"
    else:
        return "-"


def ConvertImage(input_path: str, output_path: str):
    with Image.open(input_path) as img:
        img.save(output_path, format="PNG", interlace=False)


def CreateInvoiceHeader(pdf: FPDF, show_line: bool = True):
    logo_path = urljoin(PROJECT_PATH, "utils/short-logo.png")
    # convert logo
    try:
        temp_logo_path = "/tmp/converted_image.png"
        ConvertImage(logo_path, temp_logo_path)
        logo_path = temp_logo_path
    except Exception as e:
        raise RuntimeError(f"Error converting PNG: {e}")

    # add header
    pdf.image(logo_path, x=95, y=10, w=20, h=0)
    pdf.set_y(33)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "AMRETA NETWORK", border=False, ln=True, align="C")
    pdf.set_y(38)
    pdf.cell(0, 10, "Solusi Internet Unlimited", border=False, ln=True, align="C")
    pdf.set_y(43)
    pdf.set_font("Arial", "", 10)
    pdf.cell(
        0,
        10,
        "whatsapp: 08999094340 | email: sandi@amreta.net",
        border=False,
        ln=True,
        align="C",
    )
    pdf.set_y(47)
    pdf.cell(
        0,
        10,
        "Cipacing, Jatinangor",
        border=False,
        ln=True,
        align="C",
    )
    if show_line:
        pdf.set_y(58)
        pdf.line(10, 58, 200, 58)


def CreatePDFInvoiceBody(pdf: FPDF, data):
    # invoice title
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 15, "INVOICE", border=False, ln=True, align="R")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(
        0,
        6,
        f'Periode {DateIDFormatter(data.get("due_date",None))}',
        border=False,
        ln=True,
        align="R",
    )
    if data.get("status", None) == "UNPAID":
        pdf.set_text_color(255, 28, 40)
    pdf.cell(
        0,
        6,
        paymentStatusFormatter(data.get("status", "PAID")),
        border=False,
        ln=True,
        align="R",
    )

    # customer welcome
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 12)
    pdf.cell(
        0, 10, "Kepada Yth. Pelanggan Amreta Network", border=False, ln=False, align="L"
    )
    pdf.ln(15)
    # service number
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 7, "Nomor Layanan", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 7, ":", border=False, ln=False, align="L")
    pdf.cell(
        0, 7, str(data.get("service_number", "-")), border=False, ln=True, align="L"
    )
    # name
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 7, "Nama Pelanggan", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 7, ":", border=False, ln=False, align="L")
    pdf.cell(
        0,
        7,
        data.get("customer", "-").get("name", "-"),
        border=False,
        ln=True,
        align="L",
    )
    # address
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 7, "Alamat", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 7, ":", border=False, ln=False, align="L")
    pdf.multi_cell(
        0,
        7,
        data.get("customer", "-").get("address", "-"),
        border=False,
        align="L",
    )
    # phone number
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 7, "Nomor Telepon", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 7, ":", border=False, ln=False, align="L")
    pdf.cell(
        0,
        7,
        f'0{data.get("customer","-").get("phone_number","-")}',
        border=False,
        ln=True,
        align="L",
    )
    # invoice date
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 7, "Tanggal Invoice", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 7, ":", border=False, ln=False, align="L")
    pdf.cell(
        0,
        7,
        DateIDFormatter(data.get("created_at", None)),
        border=False,
        ln=True,
        align="L",
    )
    # due date
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 7, "Jatuh Tempo", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 7, ":", border=False, ln=False, align="L")
    pdf.cell(
        0,
        7,
        DateIDFormatter(data.get("due_date", None)),
        border=False,
        ln=True,
        align="L",
    )
    # package
    pdf.ln(7)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(20, 7, "No", border=False, ln=False, align="L")
    pdf.cell(150, 7, "Paket", border=False, ln=False, align="L")
    pdf.cell(0, 7, "Harga", border=False, ln=True, align="R")
    package_items = data.get("package", []) + data.get("add_on_packages", [])
    for index, item in enumerate(package_items):
        pdf.set_font("Arial", "", 12)
        pdf.cell(20, 7, str(index + 1), border=False, ln=False, align="L")
        pdf.cell(150, 7, item.get("name", "-"), border=False, ln=False, align="L")
        pdf.cell(
            0,
            7,
            f'Rp{ThousandSeparator(item.get("price",0).get("regular",0))}',
            border=False,
            ln=True,
            align="R",
        )
    subtotal = int(data.get("package_amount", 0)) + int(
        data.get("add_on_package_amount", 0)
    )
    # amount
    pdf.set_font("Arial", "B", 12)
    pdf.cell(
        0,
        7,
        f"Sub Total: Rp{ThousandSeparator(subtotal)}",
        border=False,
        ln=False,
        align="R",
    )
    pdf.ln(7)
    pdf.cell(
        0,
        7,
        f'PPN: Rp{ThousandSeparator(data.get("ppn"))}',
        border=False,
        ln=False,
        align="R",
    )
    pdf.ln(7)
    pdf.cell(
        0,
        7,
        f'Kode Unik: {str(data.get("unique_code",0))}',
        border=False,
        ln=False,
        align="R",
    )
    pdf.ln(7)
    pdf.cell(
        0,
        7,
        f'Total Tagihan: Rp{ThousandSeparator(data.get("amount"))}',
        border=False,
        ln=False,
        align="R",
    )
    pdf.ln(10)
    # notes
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(255, 28, 40)
    pdf.cell(0, 7, "CATATAN:", border=False, ln=False, align="L")
    pdf.ln(7)
    pdf.set_font("Arial", "I", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(
        0,
        7,
        f'*Mohon melakukan pembayaran dengan nominal tepat Rp{ThousandSeparator(data.get("amount"))} sesuai Total Tagihan*',
        border=False,
        ln=False,
        align="L",
    )
    pdf.ln(15)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(
        0,
        7,
        "Pembayaran Bisa Dilakukan Menggunakan Metode Transfer",
        border=False,
        ln=False,
        align="L",
    )
    pdf.ln(7)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(
        0,
        7,
        "Konfirmasi Pembayaran Anda Melalui Kontak Kami:",
        border=False,
        ln=False,
        align="L",
    )
    # admin contact
    pdf.ln(7)
    pdf.set_font("Arial", "", 12)
    pdf.cell(30, 7, "Email", border=False, ln=False, align="L")
    pdf.cell(2, 7, ":", border=False, ln=False, align="L")
    pdf.cell(2, 7, "sandi@amreta.net", border=False, ln=False, align="L")
    pdf.ln(7)
    pdf.set_font("Arial", "", 12)
    pdf.cell(30, 7, "Whatsapp", border=False, ln=False, align="L")
    pdf.cell(2, 7, ":", border=False, ln=False, align="L")
    pdf.cell(2, 7, "08999094340", border=False, ln=False, align="L")
    # footer
    pdf.set_y(-30)
    pdf.set_font("Arial", "BI", 12)
    pdf.cell(
        0,
        7,
        "Terimakasih Telah Melakukan Pembayaran Tepat Waktu ^_^",
        border=False,
        ln=False,
        align="C",
    )


def CreateThermalInvoiceBody(pdf: FPDF, data):
    pdf.set_font("Arial", "", 10)
    pdf.set_y(60)
    pdf.cell(0, 6, "========================================", ln=True, align="C")
    pdf.set_y(65)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Struk Pembayaran Tagihan", ln=True, align="C")
    pdf.set_y(70)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, "========================================", ln=True, align="C")
    pdf.set_x(65)
    pdf.cell(
        0,
        6,
        f'Nomor Layanan     : {str(data.get("service_number","-"))}',
        ln=True,
        align="L",
    )
    pdf.set_x(65)
    pdf.cell(
        0, 6, f'Nama                     : {data.get("name","-")}', ln=True, align="L"
    )
    pdf.set_x(65)
    pdf.cell(
        0,
        6,
        f'Status Tagihan      : {paymentStatusFormatter(data.get("status","PAID"))}',
        ln=True,
        align="L",
    )
    pdf.set_x(65)
    pdf.cell(
        0,
        6,
        f'Jatuh Tempo         : {DateIDFormatter(data.get("due_date",None))}',
        ln=True,
        align="L",
    )
    pdf.set_x(65)
    pdf.cell(
        0,
        6,
        f"Dicetak Pada         : {DateIDFormatter(str(GetCurrentDateTime()))}",
        ln=True,
        align="L",
    )
    pdf.cell(0, 6, "========================================", ln=True, align="C")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Informasi Paket", ln=True, align="C")
    pdf.set_x(65)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(50, 6, "Nama Paket", border=False, ln=False, align="L")
    pdf.cell(30, 6, "Harga", border=False, ln=True, align="R")
    package_items = data.get("package", []) + data.get("add_on_packages", [])
    for index, item in enumerate(package_items):
        pdf.set_font("Arial", "", 10)
        pdf.set_x(65)
        pdf.cell(50, 6, item.get("name", "-"), border=False, ln=False, align="L")
        pdf.cell(
            30,
            6,
            f'Rp{ThousandSeparator(item.get("price",0).get("regular",0))}',
            border=False,
            ln=True,
            align="R",
        )
    pdf.cell(0, 6, "========================================", ln=True, align="C")
    pdf.set_font("Arial", "B", 10)
    subtotal = int(data.get("package_amount", 0)) + int(
        data.get("add_on_package_amount", 0)
    )
    pdf.cell(0, 6, f"Sub Total : Rp{ThousandSeparator(subtotal)}", ln=True, align="C")
    pdf.cell(0, 6, f'PPN : Rp{ThousandSeparator(data.get("ppn"))}', ln=True, align="C")
    pdf.cell(
        0,
        6,
        f'Kode Unik : {ThousandSeparator(data.get("unique_code"))}',
        ln=True,
        align="C",
    )
    pdf.cell(
        0,
        6,
        f'Total Tagihan : Rp{ThousandSeparator(data.get("amount"))}',
        ln=True,
        align="C",
    )
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, "========================================", ln=True, align="C")
    pdf.cell(0, 6, "~Terimakasih~", ln=True, align="C")
    pdf.cell(0, 6, "Amreta Network", ln=True, align="C")
    pdf.cell(0, 6, "========================================", ln=True, align="C")


def CreateInvoicePDF(data: list) -> BytesIO:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    for item in data:
        pdf.add_page()

        # create header
        CreateInvoiceHeader(pdf)

        # create body
        CreatePDFInvoiceBody(pdf, item)

    # save to pdf
    pdf_bytes = BytesIO()
    pdf_output = pdf.output(dest="S").encode("latin1")
    pdf_bytes.write(pdf_output)
    pdf_bytes.seek(0)
    return pdf_bytes


def CreateInvoiceThermal(data: list):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    for item in data:
        pdf.add_page()
        # create header
        CreateInvoiceHeader(pdf, False)
        # create body
        CreateThermalInvoiceBody(pdf, item)

    # save to pdf
    pdf_bytes = BytesIO()
    pdf_output = pdf.output(dest="S").encode("latin1")
    pdf_bytes.write(pdf_output)
    pdf_bytes.seek(0)
    return pdf_bytes
