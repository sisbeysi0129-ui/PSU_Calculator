from flask import Flask, render_template, request
import json
import os
import math
import re

app = Flask(__name__)


# =========================
# 데이터 로드
# =========================

def load_data(filename):
    path = os.path.join("data", filename)

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


cpus = load_data("cpu.json")
gpus = load_data("gpu.json")
motherboards = load_data("motherboard.json")
rams = load_data("ram.json")
ssds = load_data("ssd.json")
hdds = load_data("hdd.json")
psus = load_data("psu.json")


# =========================
# ID로 부품 찾기
# =========================

def find_part(data, part_id):
    if not part_id:
        return None

    part_id = str(part_id)

    return next(
        (
            x for x in data
            if str(x.get("id")) == part_id
        ),
        None
    )


def cpu_socket(cpu):
    """Return the socket used by the CPU models supported in this calculator."""
    manufacturer = str(cpu.get("manufacturer", "")).strip().lower()
    model = str(cpu.get("model", "")).upper()

    if manufacturer == "intel":
        match = re.search(r"\bCORE\s+I[3579]-(\d{3,5})", model)
        if match:
            number = match.group(1)
            generation = 1 if len(number) == 3 else int(number[:2] if len(number) == 5 else number[0])
            if generation == 1:
                return "LGA1156"
            if generation in (2, 3):
                return "LGA1155"
            if generation == 4:
                return "LGA1150"
            if generation in (6, 7):
                return "LGA1151"
            if generation in (8, 9):
                return "LGA1151-v2"
        if any(f"-{generation}" in model for generation in ("10", "11")):
            return "LGA1200"
        if any(f"-{generation}" in model for generation in ("12", "13", "14")):
            return "LGA1700"

    if manufacturer == "amd":
        match = re.search(r"\bRYZEN\s+[3579]\s+(\d{4,5})", model)
        if match:
            generation = int(match.group(1)[0])
            if generation in (1, 2, 3, 5):
                return "AM4"
            if generation in (7, 9):
                return "AM5"

    return ""


# =========================
# 메인 페이지
# =========================

@app.route("/", methods=["GET", "POST"])
def home():

    result = None
    error = None

    if request.method == "POST":

        # -------------------------
        # 선택값
        # -------------------------

        cpu_id = request.form.get("cpu")
        gpu_id = request.form.get("gpu")

        try:
            ram_count = int(request.form.get("ram_count", 2))
        except (ValueError, TypeError):
            ram_count = 2

        if ram_count not in (1, 2, 4):
            ram_count = 2

        nvme_id = request.form.get("nvme")

        try:
            nvme_count = int(
                request.form.get("nvme_count", 0)
            )
        except (ValueError, TypeError):
            nvme_count = 0

        sata_id = request.form.get("sata_ssd")

        try:
            sata_count = int(
                request.form.get("sata_ssd_count", 0)
            )
        except (ValueError, TypeError):
            sata_count = 0

        hdd_id = request.form.get("hdd")

        try:
            hdd_count = int(
                request.form.get("hdd_count", 0)
            )
        except (ValueError, TypeError):
            hdd_count = 0

        try:
            fan_count = int(
                request.form.get("fans", 0)
            )
        except (ValueError, TypeError):
            fan_count = 0

        try:
            cooler_power = int(
                request.form.get("cooler", 5)
            )
        except (ValueError, TypeError):
            cooler_power = 5


        # -------------------------
        # 필수 부품 확인
        # -------------------------

        if not cpu_id:
            error = "CPU를 선택해주세요."

        elif not gpu_id:
            error = "GPU를 선택해주세요."

        elif nvme_count > 0 and not nvme_id:
            error = "NVMe SSD 수량을 선택하려면 모델도 선택해주세요."

        elif sata_count > 0 and not sata_id:
            error = "SATA SSD 수량을 선택하려면 모델도 선택해주세요."

        elif hdd_count > 0 and not hdd_id:
            error = "HDD 수량을 선택하려면 모델도 선택해주세요."


        if error:

            return render_template(
                "index.html",

                cpus=cpus,
                gpus=gpus,
                motherboards=motherboards,
                rams=rams,
                ssds=ssds,
                hdds=hdds,

                result=None,
                error=error
            )


        # -------------------------
        # 부품 찾기
        # -------------------------

        cpu = find_part(
            cpus,
            cpu_id
        )

        gpu = find_part(
            gpus,
            gpu_id
        )

        # -------------------------
        # NVMe
        # -------------------------

        nvme = find_part(
            ssds,
            nvme_id
        )


        # -------------------------
        # SATA SSD
        # -------------------------

        sata_ssd = find_part(
            ssds,
            sata_id
        )


        # -------------------------
        # HDD
        # -------------------------

        hdd = find_part(
            hdds,
            hdd_id
        )


        # -------------------------
        # 데이터 확인
        # -------------------------

        if not cpu or not gpu:

            error = "선택한 부품 데이터를 찾을 수 없습니다."

            return render_template(
                "index.html",

                cpus=cpus,
                gpus=gpus,
                motherboards=motherboards,
                rams=rams,
                ssds=ssds,
                hdds=hdds,

                result=None,
                error=error
            )

        # =========================
        # 전력 계산
        # =========================

        cpu_power = float(
            cpu.get("max_power", 0)
        )

        gpu_power = float(
            gpu.get("max_power", 0)
        )

        # -------------------------
        # 플랫폼 기본 전력
        # 메인보드는 일반적인 기본값으로, RAM은 개수만 반영해 계산한다.
        # -------------------------

        platform_power = 45 + (ram_count * 5)


        # -------------------------
        # NVMe 전력
        # -------------------------

        nvme_power = 0

        if nvme:

            nvme_power = (
                float(
                    nvme.get("power", 0)
                )
                * nvme_count
            )


        # -------------------------
        # SATA SSD 전력
        # -------------------------

        sata_power = 0

        if sata_ssd:

            sata_power = (
                float(
                    sata_ssd.get("power", 0)
                )
                * sata_count
            )


        # -------------------------
        # HDD 전력
        # -------------------------

        hdd_power = 0

        if hdd:

            hdd_power = (
                float(
                    hdd.get("power", 0)
                )
                * hdd_count
            )


        # -------------------------
        # 시스템 팬
        # -------------------------

        fan_power = fan_count * 3


        # -------------------------
        # 총 소비전력
        # -------------------------

        total_power = (
            cpu_power
            + gpu_power
            + platform_power
            + nvme_power
            + sata_power
            + hdd_power
            + fan_power
            + cooler_power
        )


        # -------------------------
        # 25% 여유
        # -------------------------

        recommended_power = (
            total_power * 1.25
        )


        # -------------------------
        # PSU 권장 용량
        # 총 소비전력에 25% 여유를 적용하고,
        # 업그레이드를 고려해 100W를 추가한다.
        # -------------------------

        minimum_psu = int(
            math.ceil(
                recommended_power / 50
            ) * 50
        )

        recommended_psu = (
            minimum_psu + 100
        )

        high_psu = (
            minimum_psu + 200
        )

        recommended_psus = sorted(
            (
                psu for psu in psus
                if int(psu.get("watt", 0)) >= recommended_psu
            ),
            key=lambda psu: (
                int(psu.get("watt", 0)),
                psu.get("brand", ""),
                psu.get("model", "")
            )
        )[:3]


        # =========================
        # 결과
        # =========================

        result = {

            "cpu":
                f'{cpu.get("manufacturer", "")} '
                f'{cpu.get("model", "")}',

            "gpu":
                f'{gpu.get("manufacturer", "")} '
                f'{gpu.get("model", "")}',

            "ram_count": ram_count,

            # -------------------------
            # NVMe
            # -------------------------

            "nvme":
                (
                    f'{nvme.get("manufacturer", "")} '
                    f'{nvme.get("model", "")} '
                    f'{nvme.get("capacity", "")}'
                    if nvme
                    else "선택하지 않음"
                ),

            "nvme_count":
                nvme_count,


            # -------------------------
            # SATA SSD
            # -------------------------

            "sata_ssd":
                (
                    f'{sata_ssd.get("manufacturer", "")} '
                    f'{sata_ssd.get("model", "")} '
                    f'{sata_ssd.get("capacity", "")}'
                    if sata_ssd
                    else "선택하지 않음"
                ),

            "sata_count":
                sata_count,


            # -------------------------
            # HDD
            # -------------------------

            "hdd":
                (
                    f'{hdd.get("manufacturer", "")} '
                    f'{hdd.get("model", "")} '
                    f'{hdd.get("capacity", "")}'
                    if hdd
                    else "선택하지 않음"
                ),

            "hdd_count":
                hdd_count,


            # -------------------------
            # 팬
            # -------------------------

            "fan_count":
                fan_count,


            # -------------------------
            # 전력
            # -------------------------

            "cpu_power":
                cpu_power,

            "gpu_power":
                gpu_power,

            "platform_power":
                platform_power,

            "nvme_power":
                nvme_power,

            "sata_power":
                sata_power,

            "hdd_power":
                hdd_power,

            "fan_power":
                fan_power,

            "cooler_power":
                cooler_power,


            # -------------------------
            # 총 전력
            # -------------------------

            "total_power":
                round(total_power),

            "recommended_power":
                round(recommended_power),

            # -------------------------
            # PSU
            # -------------------------

            "minimum_psu":
                minimum_psu,

            "recommended_psu":
                recommended_psu,

            "high_psu":
                high_psu,

            "recommended_psus":
                recommended_psus
        }


    # =========================
    # 페이지 출력
    # =========================

    return render_template(
        "index.html",

        cpus=cpus,
        gpus=gpus,
        motherboards=motherboards,
        rams=rams,
        ssds=ssds,
        hdds=hdds,

        result=result,
        error=error
    )


# =========================
# 실행
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
