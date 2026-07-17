# TOÁN HỌC HÓA VIỆC XÂY DỰNG DATASET
## Mô hình sinh dữ liệu (Data-Generating Process) cho bài toán cắt chặng – ghép chặng – giá linh hoạt đường sắt Việt Nam

**Tài liệu này định nghĩa:** (i) cấu trúc toán học của bài toán; (ii) DGP tham số hóa đầy đủ; (iii) các định lý/tính chất được khai thác; (iv) quy tắc hiệu chuẩn với số liệu thực ở Tài liệu 01.

**Nguyên tắc tối thượng:**
> Dataset không phải là "một đống số ngẫu nhiên trông giống thật". Dataset là **một mô hình xác suất có tham số đã được hiệu chuẩn**, trong đó **giá và quyết định tồn kho là biến nội sinh tác động nhân quả lên cầu**. Nếu giá không ảnh hưởng đến hành vi trong DGP, thì mọi thuật toán định giá đều cho cùng một kết quả và bài dự thi vô nghĩa.

---

## 1. Ký hiệu và cấu trúc không gian

### 1.1. Tuyến là đồ thị đường thẳng

Tuyến $L$ có tập ga có tác nghiệp $\mathcal{S} = \{s_0, s_1, \dots, s_N\}$, sắp thứ tự theo lý trình $d_0 < d_1 < \dots < d_N$ (km, gốc tại ga Hà Nội, $d_N = 1726$).

**Khu gian** (segment) thứ $e$: $\epsilon_e = (s_{e-1}, s_e)$, $e \in \mathcal{E} = \{1,\dots,N\}$, chiều dài $\ell_e = d_e - d_{e-1}$.

**Hành trình / cặp O–D**: $\omega = (i,j)$ với $0 \le i < j \le N$ (chiều lẻ, Bắc→Nam). Tập O–D của tàu $t$ có tập ga dừng $\mathcal{S}_t \subseteq \mathcal{S}$:
$$\Omega_t = \{(i,j) : s_i, s_j \in \mathcal{S}_t,\ i<j\}, \qquad |\Omega_t| = \binom{|\mathcal{S}_t|}{2}$$

Với SE1 dừng 22 ga: $\binom{22}{2} = 231$ cặp O–D. Với SE5/SE7 dừng ~35 ga: $\binom{35}{2}=595$ cặp. **Đây là con số làm bài toán khó**: một chuyến tàu không phải 1 sản phẩm, mà là 231–595 sản phẩm chia sẻ chung tài nguyên.

### 1.2. Ma trận phủ khu gian (incidence matrix)

$$A \in \{0,1\}^{|\mathcal{E}| \times |\Omega_t|}, \qquad A_{e,(i,j)} = \mathbb{1}[\,i < e \le j\,]$$

**Tính chất then chốt (C1P):** mỗi **cột** của $A$ là một dãy các số 1 **liên tiếp** (consecutive-ones property), vì hành trình $(i,j)$ phủ đúng khối khu gian $\{i+1,\dots,j\}$.

> **Định lý 1 (Tính đơn modula toàn phần).** Ma trận 0–1 có tính chất "các số 1 liên tiếp theo cột" (ma trận khoảng — *interval matrix*) là **hoàn toàn đơn modula (totally unimodular, TU)**.
>
> **Hệ quả 1.1.** Đa diện $\{y \ge 0 : Ay \le C\}$ với $C$ nguyên có **mọi đỉnh nguyên**. Do đó bài toán phân bổ tĩnh (quota) dạng LP **không có khe hở nguyên (integrality gap)**: nghiệm LP đã là nghiệm nguyên tối ưu. **Không cần MILP cho lõi bài toán quota.** Đây là lý do bài toán 1.726 km với hàng trăm O–D vẫn giải được theo thời gian thực (mục 15 đề bài: "near real-time").

### 1.3. Chỗ ngồi và bài toán tô màu đồ thị khoảng

Mỗi chỗ (seat/berth) $k$ trong loại chỗ $c$ của chuyến $r$ được gán một tập hành trình $\Pi_k$ gồm các **khoảng nửa mở** $[i,j)$ **đôi một rời nhau**.

Gọi tải khu gian: $x_e = \sum_{\omega \in \Omega} A_{e\omega}\, q_\omega$ với $q_\omega$ = số vé đã bán cho O–D $\omega$. Gọi $\omega^\* = \max_e x_e$ (clique số của đồ thị khoảng).

> **Định lý 2 (Gallai / đồ thị khoảng là đồ thị hoàn hảo).** Với một tập vé đã bán, **tồn tại một phép gán chỗ không phải đổi chỗ** khi và chỉ khi $\;x_e \le C_c\;\forall e$, trong đó $C_c$ là số chỗ loại $c$. Số chỗ tối thiểu cần dùng đúng bằng $\max_e x_e$, và thuật toán **quét trái→phải, gán chỗ rảnh đầu tiên (greedy/first-fit theo ga đi)** đạt tối ưu trong $O(n\log n)$.

**Ba hệ quả trực tiếp cho bài toán:**

1. **Tách bài toán:** "bán bao nhiêu vé cho O–D nào" (quota, §5) **tách được** khỏi "gán chỗ nào" (assignment, §6). Chỉ cần đảm bảo ràng buộc tải khu gian, việc gán chỗ *luôn* khả thi mà không phải đổi chỗ.
2. **"Khoảng trống ghế" (gap) KHÔNG phải là hệ quả tất yếu của cầu** — nó là **hệ quả của việc gán chỗ trực tuyến (online)**, khi ta phải gán ngay lúc khách mua, chưa biết tương lai. Bài toán ghép chặng vì thế thực chất là **online interval graph colouring**.
3. **Cận lý thuyết cho phần "ghép chặng":** thuật toán online tốt nhất (Kierstead–Trotter) dùng không quá $3\omega^\*-2$ màu và cận này là chặt; First-Fit dùng $\Theta(\omega^\*)$ màu với hằng số đã biết nằm trong khoảng $[5,8]$. **Kết luận thực hành: hệ thống hiện tại (gán chỗ tuần tự) về lý thuyết có thể lãng phí tới ~3× công suất so với tối ưu offline** ⇒ đây chính là dư địa mà "ghép chặng + tái phân bổ chỗ" khai thác. **Con số này phải được đo trên dataset** (xem §10, chỉ số $\mathrm{RO}$).

### 1.4. Chỉ số chuyến và không gian sản phẩm

Chuyến tàu chạy (train-run): $r = (t, D)$ với $t$ = mác tàu, $D$ = ngày khởi hành.
Sản phẩm: $(r, \omega, c)$ = (chuyến, cặp O–D, loại chỗ), $c \in \mathcal{C}$ = {ngồi mềm ĐH, nằm khoang 6 T1/T2/T3, nằm khoang 4 T1/T2, VIP}.
Thời gian đặt chỗ: $u \in [0, H_r]$ = **số ngày trước khi tàu chạy** ($u=H_r$: mở bán; $u=0$: giờ tàu chạy).

---

## 2. Kiến trúc DGP tổng thể

$$\underbrace{\text{Ngoại sinh}}_{\text{lịch, thời tiết, sự kiện, giá xăng}} \;\to\; \underbrace{\Lambda_{r\omega c}}_{\text{cường độ cầu tiềm ẩn}} \;\to\; \underbrace{\text{NHPP}}_{\text{dòng yêu cầu}} \;\to\; \underbrace{\text{Choice model}}_{\text{lựa chọn}} \;\leftrightarrows\; \underbrace{\text{Chính sách giá + tồn kho}}_{\text{nội sinh}} \;\to\; \underbrace{\text{Giao dịch, hủy, log}}_{\text{dữ liệu quan sát}}$$

Vòng lặp `⇆` là điều làm dataset này khác một bộ dữ liệu tổng hợp tầm thường: **giá và tình trạng còn chỗ tại thời điểm $u$ phụ thuộc vào lịch sử bán, và ngược lại tác động lên xác suất mua**. Đây là một **hệ động lực ngẫu nhiên có điều khiển**, không phải một bảng i.i.d.

Ta lưu **cả hai tầng**:
- **Tầng tiềm ẩn (latent, chỉ dùng để chấm điểm)**: $\Lambda_{r\omega c}$, sẵn lòng chi trả (WTP) từng khách, phương án tối ưu offline. → file `_ground_truth/`.
- **Tầng quan sát (observable, giao cho thí sinh)**: log tìm kiếm, giao dịch, giá hiển thị, tồn kho, thời tiết, lịch. → file `data/`.

---

## 3. Tầng 1 — Cầu tiềm ẩn theo cặp O–D

### 3.1. Tổng nhu cầu đi lại giữa hai vùng (mô hình trọng lực)

$$T_{ij}(D) \;=\; \kappa \cdot \frac{\big(P_i\, \Theta_i(D)\big)^{\alpha}\,\big(P_j\, \Theta_j(D)\big)^{\beta}}{f(d_{ij})} \cdot \exp\!\big(g_{\text{cal}}(D) + g_{\text{ev}}(i,j,D) + g_{\text{tr}}(D)\big)$$

- $P_i$: dân số vùng thu hút của ga $i$ (**dùng ranh giới 34 tỉnh từ 01/7/2025**, SCD-2).
- $\Theta_i(D)$: chỉ số hấp dẫn du lịch/kinh tế của ga $i$ tại thời điểm $D$ (nội suy từ lượt khách du lịch tỉnh; §3.4).
- $d_{ij} = |d_j - d_i|$: cự ly đường sắt.
- Hàm ma sát: $f(d) = d^{\theta} e^{d/d_0}$ (dạng chuẩn của gravity có suy giảm mũ). Với đường sắt VN: $\theta \approx 0{,}8$–$1{,}2$; $d_0 \approx 2500$ km (rất yếu — vì đường sắt VN cạnh tranh tốt ở cự ly rất dài).

> ⚠️ **Sai lầm hay gặp:** ép $T_{ij}$ trực tiếp thành "nhu cầu đi tàu". Không đúng. $T_{ij}$ là **tổng nhu cầu đi lại mọi phương thức**. Thị phần đường sắt là **hàm phi đơn điệu của cự ly** (thấp <150 km vì xe khách thắng; đỉnh ở 300–1.000 km; giảm >1.200 km vì hàng không thắng). Nếu nhét tính phi đơn điệu này vào $f(d)$ bằng tay, ta mất khả năng để **giá tác động lên thị phần** — tức mất chính cơ chế mà dynamic pricing khai thác. **Phải tách hai tầng (§3.2).**

### 3.2. Chia sẻ phương thức (mode split) bằng logit — nơi giá đi vào mô hình

Với mỗi cặp O–D và mỗi phân khúc khách $g$ (công vụ / về quê / du lịch / thăm thân / học sinh–sinh viên), tiện ích của phương thức $m \in \{\text{sắt},\text{bay},\text{bộ},\text{cá nhân}\}$:

$$V_m^{(g)}(i,j,D) = \text{ASC}_m^{(g)} \;-\; \beta^{(g)}_{\text{cost}}\, \tilde{c}_m(i,j,D) \;-\; \beta^{(g)}_{\text{time}}\, \tau_m(i,j) \;-\; \beta^{(g)}_{\text{freq}}\,\frac{1}{\text{freq}_m} \;+\; \xi_m$$

$$\Pr(\text{sắt} \mid i,j,g,D) = \frac{e^{V_{\text{sắt}}}}{\sum_m e^{V_m}}$$

$$\boxed{\;\Lambda^{\text{sắt}}_{ij}(D) \;=\; \sum_g \pi_g(i,j,D)\; T_{ij}(D)\; \Pr(\text{sắt}\mid i,j,g,D)\;}$$

trong đó $\tilde{c}_{\text{sắt}}$ = **giá vé kỳ vọng đường sắt** (tính từ giá cơ bản, §7). Nhờ đó:
- **Độ co giãn giá theo cự ly tự sinh ra**: ở 200 km, xe khách rẻ ⇒ $\partial \ln \Lambda / \partial \ln p$ rất âm; ở 1.700 km, đối thủ là hàng không (đắt hơn nhiều) ⇒ ít co giãn hơn.
- **Cú sốc ngoại sinh cài được vào**: từ 15/7/2026 thu phí 5 dự án cao tốc Bắc–Nam ⇒ $\tilde{c}_{\text{bộ}} \uparrow$ ⇒ thị phần sắt $\uparrow$. Giá nhiên liệu 2026 biến động ⇒ tác động cả $\tilde c_{\text{sắt}}$ (VNR tăng 5–10% rồi giảm 10% từ 1/7) và $\tilde c_{\text{bộ}}$. **Đây là các biến công cụ (instrumental variables) tự nhiên** — hãy cố ý đưa vào để đội có thể ước lượng độ co giãn không thiên lệch.

$\pi_g$ = tỷ trọng phân khúc, **phụ thuộc lịch**: quanh Tết, $\pi_{\text{về quê}}$ tăng vọt và $\beta_{\text{cost}}$ của phân khúc này thấp (buộc phải về) ⇒ **ít co giãn giá vào Tết** — khớp thực tế: giá vé Tết tăng 4–5% mà sản lượng vẫn +9,5%.

### 3.3. Bất đối xứng chiều — hiệu chuẩn bằng chính chính sách của VNR

Định nghĩa $\tau(D) = D - D_{\text{mùng 1}}(\text{năm})$ (ngày lệch so với mùng Một Tết; $\tau<0$: trước Tết).

$$\Lambda_{ij} \;\leftarrow\; \Lambda_{ij}\cdot \phi_{\text{dir}}(\tau,\ \text{sign}(j-i))$$

**Neo thực nghiệm (rất mạnh):** VNR giảm 5–15% cho **tàu chiều LẺ trước Tết (3/2–17/2)** và **chiều CHẴN sau Tết (21/2–8/3)**. Doanh nghiệp chỉ giảm giá cho chiều **rỗng**. Suy ra:
- **Trước Tết:** chiều nặng = **CHẴN** (Sài Gòn → Bắc/Trung: về quê); chiều rỗng = LẺ.
- **Sau Tết:** chiều nặng = **LẺ** (Bắc/Trung → Sài Gòn: trở lại làm việc); chiều rỗng = CHẴN.

Tham số hóa:
$$\ln \phi_{\text{dir}} = \gamma_{\text{peak}}\cdot \Big[\mathbb{1}[\text{chẵn}]\, \psi_{-}(\tau) + \mathbb{1}[\text{lẻ}]\, \psi_{+}(\tau)\Big] - \gamma_{\text{peak}}\cdot\Big[\mathbb{1}[\text{lẻ}]\,\psi_{-}(\tau) + \mathbb{1}[\text{chẵn}]\,\psi_{+}(\tau)\Big]$$
với $\psi_{-}(\tau) = \exp\!\big(-(\tau+7)^2/(2\cdot 5^2)\big)$ (đỉnh ~7 ngày trước Tết) và $\psi_{+}(\tau)=\exp\!\big(-(\tau-6)^2/(2\cdot 6^2)\big)$ (đỉnh ~mùng 5–6).

Ràng buộc hiệu chuẩn: tổng khách đợt Tết (3/2–8/3/2026) trên toàn mạng phải bằng **≈ 779.000 lượt** (§9.1).

### 3.4. Cấu trúc hấp dẫn ga và luồng bất đối xứng theo không gian

Đặt $\Theta_i(D) = \Theta_i^{\text{base}}\cdot\big(1 + \sum_{v} \eta_v\, \mathbb{1}[D \in W_v]\,\mathbb{1}[i \in \mathcal{G}_v]\big)$, $\mathcal{G}_v$ = tập ga phục vụ sự kiện $v$, $W_v$ = cửa sổ ngày.

| Ga | $P_i$ (chỉ số) | $\Theta_i^{\text{base}}$ | Sự kiện $v$ gắn kèm |
|---|---|---|---|
| Hà Nội (Km 0) | 1,00 | 1,00 | Đại hội XIV 19–23/1/2026; nhập học T8–9 |
| Thanh Hóa (~175) | 0,42 | 0,55 | Biển Sầm Sơn T5–T8 |
| Vinh (319) | 0,38 | 0,50 | Biển Cửa Lò T5–T8 |
| Đồng Hới (~522) | 0,18 | 0,60 | Phong Nha–Kẻ Bàng T4–T8 |
| Đông Hà (~622) | 0,15 | 0,25 | 27/7 tri ân |
| Huế (688) | 0,30 | 0,85 | Festival Huế |
| **Đà Nẵng (791,4)** | 0,55 | **1,00** | Lễ hội pháo hoa DIFF T6–T7 |
| Tam Kỳ (~865) | 0,20 | 0,35 | Hội An phụ cận |
| Quảng Ngãi (927,5) | 0,25 | 0,30 | – |
| Diêu Trì (1.095) | 0,28 | 0,55 | Quy Nhơn hè |
| Tuy Hòa (~1.198) | 0,18 | 0,35 | – |
| **Nha Trang (1.314,5)** | 0,35 | **0,95** | Lễ hội biển; cao điểm hè |
| Tháp Chàm (~1.408) | 0,15 | 0,30 | – |
| Bình Thuận (~1.551) | 0,20 | 0,60 | Mũi Né |
| Biên Hòa (~1.697) | 0,60 | 0,25 | KCN – luồng công nhân |
| **Sài Gòn (1.726)** | 1,00 | 0,90 | – |

*(Các giá trị là **giá trị khởi tạo**; §9 quy định thủ tục hiệu chuẩn lại bằng tối ưu.)*

**Luồng công nhân KCN** là đặc thù VN không được bỏ: cặp (Biên Hòa/Dĩ An/Sài Gòn) ↔ (Vinh/Thanh Hóa/Đồng Hới/Quảng Ngãi/Diêu Trì) chi phối hoàn toàn ma trận O–D dịp Tết, và **là cầu chặng RẤT dài** (>900 km — đúng ngưỡng VNR đặt cho giảm giá xa ngày).

---

## 4. Tầng 2 — Dòng yêu cầu theo thời gian đặt chỗ

### 4.1. Quá trình Poisson không thuần nhất (NHPP)

Với mỗi $(r,\omega)$, dòng **yêu cầu tìm kiếm** (chưa phải vé bán) là NHPP trên $[0,H_r]$ với cường độ:

$$\lambda_{r\omega}(u) \;=\; \Lambda_{r\omega}\cdot g_{\text{seg}(\omega)}(u \mid H_r), \qquad \int_0^{H_r} g(u)\,du = 1$$

Đổi biến $z = 1 - u/H_r \in [0,1]$ (0 = lúc mở bán, 1 = lúc tàu chạy). Dùng **hỗn hợp Beta**:

$$g(z) = w_0\,\delta_{0}(z) \;+\; \sum_{m=1}^{M} w_m\, \mathrm{Beta}(z; a_m, b_m), \qquad w_0 + \textstyle\sum_m w_m = 1$$

- $\delta_0$: **khối lượng điểm tại lúc mở bán** — hiện tượng có thật ("hơn 60.000 vé sau 1 tháng mở bán", "8h00 ngày 20/9 vé Tết cháy"). Với Tết, $w_0 \approx 0{,}10$–$0{,}20$.
- Thành phần "đặt sớm": $\mathrm{Beta}(2, 5)$; thành phần "đặt sát ngày": $\mathrm{Beta}(6, 1{,}5)$.

**Cấu trúc theo cự ly (bắt buộc):** $\mathbb{E}[z]$ tăng theo cự ly ngắn — khách chặng ngắn đặt muộn hơn nhiều.

| Loại hành trình | $w_0$ | $(w_1;a_1,b_1)$ sớm | $(w_2;a_2,b_2)$ muộn | $\mathbb{E}[u]$ (ngày trước) |
|---|---|---|---|---|
| Suốt / dài (≥900 km), thường | 0,02 | (0,55; 2,0; 4,0) | (0,43; 5,0; 1,8) | ~14–18 |
| Trung (300–900 km) | 0,01 | (0,35; 2,0; 3,0) | (0,64; 6,0; 1,6) | ~7–9 |
| **Ngắn (<300 km)** | 0,00 | (0,15; 2,0; 2,0) | (0,85; 8,0; 1,3) | **~2–4** |
| **Tết, chiều nặng, ≥900 km** | **0,18** | (0,62; 1,5; 6,0) | (0,20; 5,0; 2,0) | **~55–75** |

> ⭐ **Đây là trái tim kinh tế của bài toán.** Khách chặng ngắn đến **sau** khách chặng dài. Nếu mở bán chặng ngắn quá sớm, ghế bị "cắn" mất và không bán được vé suốt giá cao. Nếu giữ quá lâu, ghế chạy rỗng trên các khu gian đầu/cuối. Cơ chế "Giá vé linh hoạt" của VNR (giảm 15–35% chặng ngắn *sau khi* đã bán một phần chặng dài) chính là một luật heuristic cho bài toán thời điểm này. **Dataset phải tái tạo đúng thứ tự đến này, nếu không bài toán biến mất.**

### 4.2. Cửa sổ mở bán $H_r$ — KHÔNG phải hằng số

$$H_r = D_r - D^{\text{open}}(\text{đợt}(r))$$

| Đợt | Ngày mở bán | Ngày tàu chạy | $H$ (ngày) |
|---|---|---|---|
| Tết Bính Ngọ | 20/9/2025 (tập thể 15–19/9) | 3/2 – 8/3/2026 | **136 – 169** |
| Hè 2026 | ~11/4/2026 | 15/5 – 16/8/2026 | 34 – 127 |
| Sau hè 2026 | ~4/7/2026 | 17/8 – 30/12/2026 | 44 – 179 |
| Ngày thường | cuốn chiếu | – | 60–90 (giả định) |

Đây là **cắt cụt trái (left truncation)** cấu trúc: không thể có giao dịch với $u > H_r$. Mọi mô hình booking curve phải điều kiện hóa theo $H_r$; nếu không, giai đoạn Tết (H=169) và giai đoạn hè (H=34) bị trộn ⇒ đường cong đặt chỗ trung bình vô nghĩa.

### 4.3. Biến lịch phải là ÂM LỊCH TƯƠNG ĐỐI

$$\text{cal}(D) = \big(\tau(D),\ \text{dow}(D),\ \mathbb{1}[\text{nghỉ lễ}],\ \text{dist}_{\text{lễ}}(D),\ \text{tuần trong năm}\big)$$

$\tau(D) = D - D_{\text{mùng1}}$: Tết 2024 = 10/2, **2025 = 29/1**, **2026 = 17/2**, 2027 = 6/2.
Dùng `month-of-year` là **sai về mặt thống kê**: đỉnh Tết trượt 21 ngày giữa 2025 và 2026 ⇒ cùng "tháng 2" nhưng 2025 là hậu Tết, 2026 là tiền Tết. Fourier theo $\tau$ + Fourier theo ngày dương lịch (mùa du lịch, thời tiết) là biểu diễn đúng:
$$g_{\text{cal}}(D) = \sum_{k=1}^{K_1}\Big[a_k \cos\tfrac{2\pi k\, \mathrm{doy}(D)}{365{,}25} + b_k \sin(\cdot)\Big] + \sum_{k=1}^{K_2}\Big[c_k\cos\tfrac{2\pi k\,\tau}{60} + d_k \sin(\cdot)\Big] + \sum_{h}\rho_h\, \mathrm{RBF}(D; D_h)$$
với $\mathrm{RBF}(D;D_h) = \exp(-(D-D_h)^2/2\sigma_h^2)$ cho từng kỳ nghỉ $h$ (30/4, 2/9, Giỗ Tổ, Tết Dương lịch) — **hiệu ứng lễ có "vai" trước/sau, không phải xung Dirac**.

### 4.4. Xu thế và phân rã

$$g_{\text{tr}}(D) = \underbrace{\mu_0 + \mu_1 \cdot \frac{D - D_0}{365}}_{\text{xu thế}} + \underbrace{\sum_b \nu_b\,\mathbb{1}[D \ge D_b]}_{\text{gãy chế độ}}$$
Hiệu chuẩn: $\mu_1$ sao cho tăng trưởng khách năm ≈ **+5,2%** (6T/2026 so cùng kỳ) và doanh thu ≈ **+8,4%** (chênh lệch giữa hai số này = **tăng giá bình quân ≈ +3%** — một ràng buộc kiểm tra chéo tuyệt vời).
Các $D_b$ bắt buộc: **01/01/2026** (Luật ĐS mới), **01/05/2026** (AI giá linh hoạt), **15/05/2026** (trả vé online), **01/07/2026** (giảm 10% giá do nhiên liệu), **01/07/2025** (sáp nhập tỉnh).

---

## 5. Tầng 3 — Chính sách tồn kho (điều khiển) và bài toán tối ưu

### 5.1. Bài toán LP tất định (DLP) — chuẩn để sinh nhãn và làm baseline

$$\max_{y \ge 0}\;\; \sum_{\omega \in \Omega}\; f_\omega\, y_\omega \qquad \text{s.t.} \quad A\,y \le C,\qquad y_\omega \le \mathbb{E}[D_\omega]$$

- $y_\omega$: số vé phân bổ cho O–D $\omega$; $f_\omega$: doanh thu ròng/vé; $C_e$: sức chứa khu gian $e$.
- Đối ngẫu: $\pi_e \ge 0$ = **giá thầu (bid price)** của khu gian $e$ = **chi phí cơ hội của một đơn vị công suất trên khu gian đó**.

> **Quy tắc chấp nhận theo bid price:**
> $$\text{Chấp nhận yêu cầu } (i,j) \iff f_{ij} \;\ge\; \sum_{e=i+1}^{j} \pi_e$$

**Đây chính xác là lời giải cho yêu cầu ở Mục 7 đề bài** ("đánh giá tác động tương lai của việc bán một vé cụ thể — bán vé chặng ngắn qua nút cổ chai có thể chặn mất một vé chặng dài sinh lợi"). $\sum_e \pi_e$ là **chi phí dịch chuyển (displacement cost)**. Nhờ Định lý 1, LP này là nguyên và giải bằng simplex/interior-point trong mili-giây với quy mô 1 tàu.

**Sinh nhãn (label):** với mỗi chuyến, tại mỗi mốc $u$, chạy lại DLP với $\mathbb{E}[D_\omega \mid \mathcal{F}_u]$ ⇒ lưu $\pi_e(u)$ vào bảng `bid_price_log`. Đây là **nhãn tham chiếu**, không phải nhãn "đúng tuyệt đối" (DLP là xấp xỉ bậc nhất của DP), nhưng là baseline chuẩn mực trong tài liệu Revenue Management (Talluri & van Ryzin).

### 5.2. Cận trên: bài toán offline hoàn hảo (hindsight optimum)

Sau khi đã sinh xong toàn bộ dòng yêu cầu $\{(u_n, \omega_n, c_n, \text{WTP}_n)\}$ của một chuyến, giải:

$$Z^{\text{opt}} = \max_{\chi \in \{0,1\}^n} \sum_n p_n\,\chi_n \quad \text{s.t.}\quad \sum_n A_{e\omega_n}\chi_n \le C \;\;\forall e$$

Cũng là ma trận khoảng ⇒ **TU ⇒ giải bằng LP/min-cost flow trên đường thẳng, đúng tối ưu**. $Z^{\text{opt}}$ là cận trên cho MỌI thuật toán online.

**Cận dưới:** $Z^{\text{FCFS}}$ = chính sách "ai đến trước phục vụ trước, giá cố định theo biểu" (mô phỏng đúng thực trạng "dựa trên luật cố định" mà đề bài mô tả).

> **Chỉ số vàng — Tỷ lệ cơ hội doanh thu thu được:**
> $$\mathrm{RO} = \frac{Z^{\text{policy}} - Z^{\text{FCFS}}}{Z^{\text{opt}} - Z^{\text{FCFS}}} \in [0,1]$$
> Đây là thước đo **duy nhất** không phụ thuộc quy mô/mùa vụ, cho phép so sánh công bằng giữa các đội. **Đề nghị nhóm đưa RO thành chỉ số trung tâm trong báo cáo dự thi** — nó chứng minh nhóm hiểu bài toán ở tầng lý thuyết, không chỉ tầng kỹ thuật.

### 5.3. Bài toán ghép chặng (gap merging) — phát biểu chính xác

Tại thời điểm $u$, trạng thái là tập chỗ $\{ \Pi_k \}_{k=1}^{K}$. **Khoảng trống** của chỗ $k$: các khoảng cực đại $[a,b) \subseteq [0,N)$ không bị phủ bởi $\Pi_k$.

**Bài toán ghép chặng liên tục (không đổi chỗ):** cho yêu cầu $(i,j)$, tồn tại $k$ với $[i,j) \subseteq \text{gap}(k)$? Trả lời trong $O(\log K)$ bằng cây khoảng (interval tree) / segment tree.

**Bài toán ghép chặng có đổi chỗ:** tìm dãy $k_1,\dots,k_M$ và các mốc chia $i = z_0 < z_1 < \dots < z_M = j$ sao cho $[z_{m-1}, z_m) \subseteq \text{gap}(k_m)$, **tối thiểu $M$**.
$\Rightarrow$ Đây là **bài toán phủ khoảng bằng ít khoảng nhất (minimum interval cover)** ⇒ **thuật toán tham lam quét trái→phải là tối ưu**, $O(K\log K)$.
Ràng buộc bổ sung từ đề bài (bắt buộc mô hình hóa, **không được bỏ**):
- $M \ge 2$ chỉ khi **không còn chỗ liên tục nào** (ràng buộc từ điển: ưu tiên $M=1$ tuyệt đối);
- ga chuyển $s_{z_m}$ phải có **thời gian dừng đỗ đủ** ($\text{dwell}(s_{z_m}) \ge \underline{\text{dwell}}$, ví dụ ≥ 5 phút và không phải ga chỉ dừng 2 phút giữa đêm);
- **cùng loại chỗ hoặc tương đương** ($c_{k_m} \equiv c$);
- khách **được thông báo rõ và chủ động đồng ý** ⇒ trong DGP là một **xác suất chấp nhận** $\Pr(\text{đồng ý}) = \sigma(\zeta_0 - \zeta_1 M - \zeta_2\,\mathbb{1}[\text{đêm}] - \zeta_3\,\mathbb{1}[\text{có trẻ nhỏ}])$ — tức **đề xuất đổi chỗ có thể bị từ chối và làm mất khách**;
- **loại trừ/hạn chế** với người cao tuổi, người khuyết tật, trẻ em đi một mình, người cần trợ giúp đặc biệt ⇒ **ràng buộc cứng**: $\mathbb{1}[g \in \mathcal{G}_{\text{ưu tiên}}] \Rightarrow M = 1$.

**Bài toán lấp đầy khoảng trống toàn cục (offline, dùng để sinh nhãn):** min-cost max-flow trên đồ thị đường thẳng với $E+1$ nút và cung có sức chứa $K$ ⇒ đa thức, tối ưu.

### 5.4. Xếp chỗ theo nhóm — nơi bài toán trở nên NP-khó

Nhóm $\mathcal{N}$ gồm $n$ khách cùng $(i,j)$, cần **cùng khoang/toa hoặc gần nhau**, tối thiểu chia tách:
$$\min \;\; \underbrace{\lambda_1 \sum_{\text{nhóm}} (\#\text{khoang dùng} - 1)}_{\text{chia tách}} + \underbrace{\lambda_2 \sum \#\text{đổi chỗ}}_{} + \underbrace{\lambda_3\,\text{(mất doanh thu)}}_{}$$
Đây là **bin-packing có ràng buộc kề (adjacency)** trên cấu trúc khoang 4/6 ⇒ **NP-khó**. Khuyến nghị: CP-SAT (OR-Tools) cho quy mô 1 chuyến (K ≈ 400–500 chỗ) chạy < 1s; hoặc heuristic "đặt trước nguyên khoang cho nhóm ≥ 4" (đúng thực tế: khách Tết "mua nguyên buồng").

---

## 6. Tầng 4 — Mô hình lựa chọn và tràn/thu hồi (spill & recapture)

Khi khách yêu cầu $(r,\omega,c)$ mà bị từ chối/thấy giá cao, họ **không biến mất**. Tập lựa chọn:
$$\mathcal{J} = \{\text{cùng tàu, loại chỗ khác}\} \cup \{\text{tàu khác cùng ngày}\} \cup \{\text{ngày khác } \pm 3\} \cup \{\text{phương thức khác}\} \cup \{\text{không đi}\}$$

**Logit lồng (nested logit)** — bắt buộc, vì các lựa chọn trong cùng tổ có sai số tương quan:
$$\Pr(k \mid n) = \frac{e^{V_k/\mu_n}}{\sum_{k'\in n} e^{V_{k'}/\mu_n}},\qquad \Pr(n) = \frac{e^{\mu_n I_n}}{\sum_{n'} e^{\mu_{n'} I_{n'}}},\qquad I_n = \ln\!\!\sum_{k\in n} e^{V_k/\mu_n}$$
với **$0 < \mu_n \le 1$** (điều kiện nhất quán với lý thuyết thỏa dụng ngẫu nhiên — nếu $\mu_n>1$ mô hình sinh ra đạo hàm chéo sai dấu, tức dữ liệu **phi vật lý**).

Tiện ích một phương án tàu:
$$V_{r\omega c} = \text{ASC}_{c} + \text{ASC}_{t} - \beta_{\text{p}}^{(g)}\,\frac{p_{r\omega c}(u)}{\text{thu nhập}_g} - \beta_{\text{dep}}\,\Delta_{\text{giờ}} - \beta_{\text{night}}\mathbb{1}[\text{đi đêm}] - \beta_{\text{chg}} \cdot M + \varepsilon$$

- $\text{ASC}_c$ hiệu chuẩn theo giá tương đối thực: nằm K6 T1 : T2 : T3 = **1,00 : 0,912 : 0,785** (từ SE1: 1.535.000 / 1.400.000 / 1.205.000 đ) ⇒ WTP theo tầng phải tái tạo đúng thứ tự này.
- $\beta_{\text{chg}}\cdot M$: **chi phí phi thỏa dụng của việc đổi chỗ** ⇒ giải thích vì sao "ưu tiên phương án không đổi chỗ" không chỉ là quy định mà là **tối ưu kinh tế**.

**Hệ quả bắt buộc phải xuất hiện trong dữ liệu:**
- **Buy-down**: nếu giảm giá khoang 4 quá tay, khách khoang 6 nâng hạng ⇒ mất doanh thu ròng.
- **Recapture**: đóng chặng ngắn trên SE1 ⇒ khách chạy sang SE19 hoặc NA1 (nếu có), **không mất hoàn toàn** ⇒ nếu bỏ recapture, mô hình sẽ định giá quá cao một cách hệ thống.

---

## 7. Tầng 5 — Mô hình giá (tái tạo 1:1 bộ luật VNR)

### 7.1. Giá cơ bản (base fare)

$$F^{(0)}_{t,\omega,c} \;=\; \underbrace{\rho_t}_{\text{hệ số mác tàu}} \cdot \underbrace{\varsigma_c}_{\text{hệ số loại chỗ}} \cdot \underbrace{\kappa_0\, d_\omega^{\;\theta}}_{\text{cước lũy thoái theo cự ly}}, \qquad \theta \in (0{,}85;\ 1{,}00)$$

$\theta < 1$ ⇒ **giá/km giảm dần theo cự ly** (đúng thực tế: HN–HP 102 km ≈ 780–1.270 đ/km; SG–ĐN 935 km ≈ 561 đ/km ngồi mềm; HN–SG 1.726 km ≈ 667 đ/km ngồi mềm — phần vượt của HN–SG so với SG–ĐN được hấp thụ vào $\rho_t$ của tàu chất lượng cao).

**Nhận dạng tham số (identification) — quan trọng:**
- $\theta$ nhận dạng từ **biến thiên nội bộ một mác tàu qua nhiều cặp O–D**;
- $\rho_t$ từ **hiệu ứng cố định mác tàu**;
- $\varsigma_c$ từ **hiệu ứng cố định loại chỗ**.
Hồi quy log–log:
$$\ln F^{(0)}_{t\omega c} = \ln\kappa_0 + \theta \ln d_\omega + \alpha_t + \gamma_c + \epsilon$$
Chạy trên bảng giá cào từ dsvn.vn (§Tài liệu 03, §2). **Kiểm tra**: $R^2 > 0{,}97$ là bình thường cho biểu giá quy tắc; nếu thấp hơn nhiều, chứng tỏ VNR có bảng giá theo ô O–D chứ không theo công thức ⇒ khi đó **thay $\kappa_0 d^\theta$ bằng bảng tra $F^{(0)}[i][j]$** (lưu như một ma trận tam giác trên).

Neo giá tuyệt đối (SE1, HN–SG, mùa thường): ngồi mềm ĐH **1.152.000 đ**; nằm K6 T3/T2/T1 = **1.205.000 / 1.400.000 / 1.535.000 đ**; cao nhất **~1.684.000 đ**.

### 7.2. Giá hiển thị = phép hợp thành có thứ tự (thứ tự KHÔNG giao hoán)

$$p_{r\omega c}(u,\,\text{kh}) \;=\; \mathrm{clip}\Big(\underbrace{F^{(0)}\cdot \big(1+\delta_{\text{mùa}}\big)\cdot\big(1+\delta_{\text{lead}}(u,d_\omega,t)\big)\cdot\big(1+\delta_{\text{AI}}(u,\text{state})\big)\cdot\big(1+\delta_{\text{TM}}\big)}_{\text{giá niêm yết } \tilde p},\; \underline{F},\; \overline{F}\Big)$$
$$p^{\text{cuối}} = \tilde p \cdot \Big(1 - \max_{a \in \mathcal{A}(\text{kh})} \text{giảm}_a\Big)$$

**Ba quy tắc toán học bắt buộc (rút từ văn bản pháp lý, §6 Tài liệu 01):**
1. **Giảm chính sách xã hội áp SAU cùng**, trên "giá vé bán thực tế của loại chỗ, loại tàu mà đối tượng sử dụng" ⇒ **không giao hoán** với $\delta_{\text{AI}}$. Đặt sai thứ tự ⇒ sai doanh thu và sai cả quyền lợi khách.
2. **`max`, không `∏`**: khách chỉ hưởng **một** mức ưu đãi cao nhất, không cộng dồn.
3. **`clip` vào $[\underline F, \overline F]$**: sàn (không dưới mức có lãi) và trần (giá đã duyệt) — **vi phạm = nghiệm bất khả thi, không phải là "phạt mềm"**.

### 7.3. Đặc tả $\delta$ theo đúng luật thực tế

**(a) $\delta_{\text{lead}}$ — theo lead time và cự ly (hè 2026 / sau hè 2026):**
$$\delta_{\text{lead}} =
\begin{cases}
-0{,}05 \dots -0{,}10 & u \ge 20,\ d_\omega \ge \underline{d}(t) \quad \text{(hè: SE1–12: 900km; SE21/22: 600km; SE29/30: 400km; SNT1/2: 300km)}\\
-0{,}05 \dots -0{,}15 & u \ge 10,\ \text{chặng dài} \quad \text{(sau hè)}\\
+0{,}05 \dots +0{,}07 & u \le 2 \quad \text{(hè)}\\
+0{,}03 \dots +0{,}05 & u \le 2 \quad \text{(sau hè)}\\
0 & \text{ngược lại}
\end{cases}$$
Kèm **ràng buộc số lượng**: tối đa **20 vé giảm giá cho mỗi loại chỗ trên mỗi đoàn tàu** ⇒ đây là một **quota lồng trong quota** — cần một bộ đếm trạng thái $n^{\text{disc}}_{r,c}(u)$ trong mô phỏng. Loại trừ: khoang 4 giường của SE3, SNT1/2, SPT1/2.

**(b) $\delta_{\text{lead}}$ — Tết Bính Ngọ:** $-0{,}05 \dots -0{,}15$ nếu $u \ge 10$ **và** $d_\omega > 900$ **và** (chiều lẻ ∧ $D \in$ [3/2,17/2]) ∨ (chiều chẵn ∧ $D\in$[21/2,8/3]); $-0{,}03$ nếu ga đi = Sài Gòn ∧ $D$ = 15/2/2026 ∧ $d_\omega \ge 1000$.

**(c) $\delta_{\text{AI}}$ — "Giá vé linh hoạt", chỉ hoạt động từ $D \ge$ 01/5/2026:**
$$\delta_{\text{AI}} = \begin{cases}
-\,\mathrm{clip}\big(h(\text{state}),\; 0{,}15,\; \overline{\delta}_{\text{tuyến}}\big) & \text{nếu } \omega \text{ là "chặng ngắn còn lại" và điều kiện kích hoạt đúng}\\
0 & \text{ngược lại}
\end{cases}$$
với $\overline{\delta}_{\text{tuyến}}$: chặng ngắn Thống Nhất **0,35**; Huế–ĐN **0,30**; HN–HP, HN–LC **0,25**; HN–ĐN, SG–PT/NT/QN/ĐN **0,25** (biên dưới 0,15).
**Điều kiện kích hoạt** (mô hình hóa mô tả của VNR: *"khi chuyến tàu đã bán được một phần cho hành trình dài"*):
$$\text{kích hoạt} \iff \Big(\max_e x_e(u)\big/C \;\ge\; \varrho\Big) \wedge \Big(\exists\, e \in (i,j] : x_e(u)/C \le \underline{\varrho}\Big) \wedge \big(u \le \bar u\big)$$
$\varrho \approx 0{,}5$–$0{,}7$; $\underline\varrho \approx 0{,}5$; $\bar u \approx 7$–14 ngày.
**Hiệu chuẩn bắt buộc (từ thí điểm 22–29/4/2026):** trên tập chuyến trong tuần thí điểm, mô phỏng phải tái tạo:
$$\frac{\text{tổng tiền giảm}}{\text{doanh thu gộp}} = \frac{523\text{ tr}}{2000\text{ tr} + 523\text{ tr}} \approx 20{,}7\%,\qquad \frac{\#\text{vé được giảm}}{\#\text{vé}} \approx 10{,}36\%,\qquad \frac{\text{doanh thu}}{\#\text{vé}} = \frac{2\ \text{tỷ}}{9.376} \approx 213.000\ \text{đ/vé}$$
⇒ Suy ra: **mức giảm bình quân trên các vé được giảm** $\approx 20{,}7\%/10{,}36\% \approx$ **thực chất vé được giảm có giá trị lớn hơn nhiều mức trung bình**; kiểm tra: $523\text{tr}/(0{,}1036\times 9376) \approx 538.000$ đ giảm/vé được giảm — **không nhất quán với vé chặng ngắn giá ~200k**. ⚠️ **Kết luận quan trọng:** con số 10,36% được VNR công bố là "trên tổng số hành khách **toàn đoàn tàu**", không phải trên 9.376 vé bán qua tính năng. **Đây là ví dụ điển hình vì sao mọi hằng số hiệu chuẩn phải được kiểm tra tính nhất quán bằng phép chia trước khi dùng.** Ràng buộc an toàn nên dùng: chỉ neo $\frac{523}{2523} \approx 20{,}7\%$ và giá bình quân vé ưu đãi ≈ 213.000 đ (⇒ đúng là **chặng ngắn**).

**(d) $\delta_{\text{TM}}$ — thương mại:** khứ hồi $-0{,}10$ (HN–Lào Cai SP2/4/8: $-0{,}15$); tập thể ≥20 người mua trước 10–19 ngày: $-0{,}03 \dots -0{,}09$; tập thể Tết ≥11 người: $-0{,}02\dots-0{,}12$; SE17 T7/CN/T2/T3 (21/5–16/8): $-0{,}05$; đợt 1/7–16/8/2026: $-0{,}10$ toàn tàu SE Bắc–Nam, SG–NT, HN–Vinh.

**(e) $\delta_{\text{mùa}}$:** hè 2026 $+0{,}05\dots+0{,}10$ (giá nhiên liệu); Tết 2026 $+0{,}04\dots+0{,}05$.

**(f) Ràng buộc động lực học giá (từ Mục 6.6 đề bài):**
$$|p(u) - p(u')| \le \Delta_{\max}\ \ \forall |u-u'| \le 1;\qquad p(\text{sau khi giữ chỗ}) \equiv p(\text{lúc giữ chỗ});$$
$$\frac{\partial p}{\partial(\text{số lần tìm kiếm của cùng người dùng})} = 0;\qquad p \perp\!\!\!\perp \text{đặc trưng cá nhân nhạy cảm}$$
Điều kiện độc lập cuối cùng **kiểm chứng được về mặt cấu trúc**: bảng `pricing_features` **không chứa vật lý** các cột đó (§Tài liệu 03, §5.3).

### 7.4. ⭐ Vấn đề nội sinh của giá — và cách dataset giải quyết

Trong DGP, $p$ được sinh từ trạng thái tồn kho $x_e(u)$, mà $x_e(u)$ lại là hàm của cầu quá khứ, tức là của $\Lambda$. Do đó:
$$\mathrm{Cov}(p, \epsilon_{\text{cầu}}) \ne 0 \;\Longrightarrow\; \hat\beta_{\text{OLS}}^{\,p} \text{ thiên lệch, thường sai dấu}$$
(Chuyến ế ⇒ giảm giá ⇒ quan sát "giá thấp đi kèm doanh số thấp" ⇒ hồi quy ngây thơ kết luận **giảm giá làm giảm nhu cầu**.)

**Ba cơ chế nhận dạng phải được CỐ Ý cài vào dataset:**
1. **Biến công cụ (IV) ngoại sinh**: giá nhiên liệu (tác động $\delta_{\text{mùa}}$ nhưng không tác động sở thích khách), thu phí cao tốc từ 15/7/2026, ngưỡng cự ly cứng của luật giảm giá.
2. **Thiết kế hồi quy gián đoạn (RDD)**: luật "$d_\omega \ge 900$ km mới được giảm 5–15%" tạo ra **một ngưỡng sắc nét**. So sánh cặp O–D 895 km vs 905 km ⇒ ước lượng nhân quả sạch. **Hãy đảm bảo trong tuyến có các cặp O–D nằm hai bên ngưỡng 300/400/600/900/1000 km** — đây là món quà nhận dạng miễn phí.
3. **Thăm dò ngẫu nhiên $\varepsilon$-greedy** trong Pha 3 (A/B): với xác suất $\varepsilon = 0{,}05$, gán mức giá ngẫu nhiên trong biên cho phép ⇒ tạo biến thiên ngoại sinh thuần túy. **Ghi rõ trong `quyet_dinh_ai.ly_do = 'EXPLORE'`.**

---

## 8. Tầng 6 — Hủy vé, gián đoạn, danh sách chờ

### 8.1. Hủy/trả vé (hazard model, có gãy chế độ)

Vé mua tại $u_0$ có thời điểm trả $U$ với hàm nguy cơ:
$$h(u \mid u_0, \mathbf{z}) = h_0(u)\exp\big(\varphi^\top \mathbf{z}\big)\cdot \mathbb{1}[u \ge 1\ \text{ngày}]$$
$\mathbf{z}$: cự ly, loại chỗ, Tết/không, kênh mua, **$\mathbb{1}[D \ge 15/5/2026]$ (trả vé online)**.
Ràng buộc thể chế: **cá nhân chỉ trả được khi $u \ge 1$ ngày (24h)**, tập thể $u \ge 2$ ngày (48h) ⇒ **hàm sống sót bị chặn**: $S(u) = 1$ với $u < 1$. Phí trả vé: khấu trừ **30%** giá in trên thẻ ⇒ giá trị kỳ vọng của quyền hủy = $0{,}7\,p \cdot \Pr(\text{hủy})$ — đưa vào $V_k$ để mô hình hóa "vé linh hoạt vs vé điều kiện chặt" (Mục 6.3 đề bài).
**Hiệu chuẩn:** $\mathbb{E}[\text{tỷ lệ trả vé}]$ tăng có ý nghĩa sau 15/5/2026 (đây là **giả thuyết kiểm định được** mà nhóm nên nêu trong báo cáo).

**Hệ quả sinh gap:** mỗi lần trả vé tạo ra một khoảng trống $[i,j)$ trên một chỗ ⇒ **nguồn cung "khoảng trống ghép được" chính là dòng trả vé**. Không mô phỏng trả vé ⇒ không có bài toán ghép chặng.

### 8.2. Gián đoạn tuyến (marked point process)

$$\mathcal{D} = \{(D_n,\ [\underline{e}_n, \overline{e}_n],\ \Delta_n,\ \text{sev}_n)\}_{n\ge1}$$
- **Thời điểm** $D_n$: NHPP theo tháng × vùng lý trình (Tài liệu 01, §4.2):
  $$\Lambda_{\text{gd}}(D, \text{vùng}) = \bar\lambda_{\text{vùng}}\cdot \exp\Big(\sum_k \big[a_k\cos\tfrac{2\pi k\,\mathrm{doy}}{365{,}25} + b_k \sin(\cdot)\big]\Big)$$
  Vùng Nam Trung Bộ (Km 900–1.400): đỉnh **tháng 11**; Trung Trung Bộ (Km 500–900): tháng 10–11; Bắc/Bắc Trung Bộ (Km 0–500): tháng 7–9.
- **Vị trí**: $[\underline e_n, \overline e_n]$ = khối khu gian bị phong tỏa. Neo thực tế: **Km1123+600–Km1139+100**, **Km1204+200–Km1219+742**, **Km1337+900–Km1339+850** (đợt 11/2025).
- **Thời lượng** $\Delta_n \sim \text{Lognormal}(\mu_\Delta, \sigma_\Delta)$ với $\text{median} \approx 8$ ngày (đợt 11/2025: "thông tuyến sau 8 ngày"), đuôi dài tới **20+ ngày** (hầm Bãi Gió/Chí Thạnh 2024).
- **Cơ chế tác động (bắt buộc đúng, không được hủy ngẫu nhiên đều):**
  $$\text{Vé } \omega \text{ bị ảnh hưởng} \iff \exists e \in (i,j] \cap [\underline e_n, \overline e_n]$$
  ⇒ **vé chặng dài bị ảnh hưởng nhiều hơn theo đúng tỷ lệ độ dài hành trình** ⇒ **tự động tái tạo được** cơ chế chọn mẫu: giá trị hoàn vé bình quân đợt 11/2025 (**≈ 615.000 đ/vé**) **cao hơn** giá vé bình quân năm (**≈ 514.000 đ/vé**). Đây là một **kiểm định hiệu chuẩn (calibration test) sắc bén**: nếu mô phỏng cho ra hoàn vé bình quân ≈ giá vé bình quân, tức là bạn đã hủy ngẫu nhiên — **sai**.
- **Xử lý**: (i) hủy chuyến & hoàn 100% (không khấu trừ 30%); (ii) **chuyển tải bằng đường bộ** giữa hai ga biên (neo thực tế: **ga Tuy Hòa ↔ ga Giã** từ 23/11/2025) ⇒ tàu chạy cụt: $\mathcal{S}_t \to \mathcal{S}_t \cap [0, \underline e_n]$ và $\mathcal{S}_t \cap [\overline e_n, N]$ ⇒ **sinh ra một cấu trúc O–D hoàn toàn mới trong thời gian phong tỏa**.
- **Hiệu chuẩn năm:** tổng chuyến hủy/năm ≈ **> 300**; tổng khách chuyển tải ≈ **8.500**.

### 8.3. Danh sách chờ (waitlist) — hàng đợi có khớp nối

Khách bị từ chối với xác suất $\varsigma$ (hàm của mức độ linh hoạt) sẽ vào hàng chờ với **tập ưu tiên linh hoạt** $\mathcal{F} = (\text{ngày} \pm k,\ \text{loại chỗ chấp nhận},\ \mathbb{1}[\text{chấp nhận đổi chỗ}])$.
Khi có vé trả tại $u$, hệ thống khớp và **giữ chỗ tạm thời trong $T_{\text{hold}}$ phút để thanh toán**; xác suất thanh toán $\Pr(\text{pay} \mid \text{hold}) = \sigma(\cdot)$ giảm theo thời gian chờ ⇒ **đây là một bài toán khớp nối trực tuyến (online matching)**, và tỷ lệ thanh toán là một tham số cần lưu (mặc định 0,6–0,75).

---

## 9. Hiệu chuẩn: bài toán khớp mô men (moment matching)

### 9.1. Hệ ràng buộc hiệu chuẩn (tất cả từ nguồn chính thống, Tài liệu 01)

Gọi $\vartheta$ = vectơ tham số DGP. Giải:
$$\hat\vartheta = \arg\min_{\vartheta}\;\; \big(\mathbf{m}(\vartheta) - \mathbf{m}^{\text{thực}}\big)^\top W \big(\mathbf{m}(\vartheta) - \mathbf{m}^{\text{thực}}\big)$$
(phương pháp **mô men mô phỏng — Simulated Method of Moments**, McFadden 1989; $W$ = ma trận trọng số, dùng nghịch đảo phương sai).

| # | Mô men $m$ | Giá trị thực $m^{\text{thực}}$ | Nguồn |
|---|---|---|---|
| M1 | Khách 6T/2026 | 3,90 triệu lượt | VNR |
| M2 | Tăng trưởng khách YoY | +5,2% | VNR |
| M3 | Doanh thu vận tải 6T/2026 | 2.921,2 tỷ (+8,4%) | VNR |
| M4 | Doanh thu HK Traravico 6T/2026 | 2.003 tỷ (+10,8%) | Traravico |
| M5 | **Giá vé bình quân/lượt** | **≈ 514.000 đ** | M4/M1 |
| M6 | Khách đợt Tết Bính Ngọ | 779.000 (+9,5%) | Traravico |
| M7 | Doanh thu đợt Tết | 556 tỷ (+12,4%) | Traravico |
| M8 | **Giá vé bình quân Tết** | **≈ 714.000 đ** (= 1,39 × M5) | M7/M6 |
| M9 | Hệ số sử dụng chỗ (cuối T4/2026) | **79%** | VNR |
| M10 | Cung vé đi suốt Tết | 330.000 (55 đoàn/ngày, >800 toa) | Traravico |
| M11 | Cung vé đi suốt hè | ~1.500.000 (15/5–16/8) | Traravico |
| M12 | Chuyến hủy do thiên tai/năm | > 300 | VNR |
| M13 | Khách chuyển tải/năm | ~8.500 | VNR |
| M14 | Hoàn vé đợt lũ 11/2025 | 39.000 vé / 24 tỷ ⇒ **615.000 đ/vé** | Bộ Xây dựng |
| M15 | Tỷ lệ giảm giá của AI trên doanh thu gộp | ≈ 20,7% | VNR (thí điểm) |
| M16 | Tăng trưởng DT theo tuyến | HN–LC +27%; HN–ĐN +12%; HN–HP +12% | Traravico |
| M17 | Tàu di sản Huế–ĐN | SL +11%, DT +41% ⇒ **giá bình quân +27%** | Traravico |
| M18 | Charter | 5.400 khách / 16 tỷ ⇒ ~2,96 tr/khách | Traravico |

**Kiểm tra nhất quán nội tại (bắt buộc chạy trước khi tin M):**
- M2 & M3: khách +5,2%, doanh thu +8,4% ⇒ **giá bình quân +3,0%** $\big(1{,}084/1{,}052 = 1{,}030\big)$. Hợp lý với "giá vé hè +5–10%, giảm 10% từ 1/7". ✔
- M17: DT +41% / SL +11% ⇒ giá bình quân +27% cho tàu di sản — hợp lý (nâng cấp sản phẩm). ✔
- M8/M5 = 1,39 ⇒ Tết đắt hơn 39% trong khi **giá vé Tết chỉ tăng 4–5%** ⇒ **~34 điểm % còn lại đến từ MIX (cự ly dài hơn, hạng chỗ cao hơn)**. ⇒ **Đây là ràng buộc chẩn đoán mạnh nhất trong toàn bộ tài liệu**: nếu mô phỏng của bạn tái tạo M8 chủ yếu bằng cách nâng giá, mô hình sai. Phải tái tạo bằng **dịch chuyển phân phối cự ly O–D** về phía chặng >900 km trong dịp Tết. ✔

### 9.2. Quy trình hiệu chuẩn 3 giai đoạn

1. **Cố định (fix):** cấu trúc mạng, lý trình, biểu đồ chạy tàu, thành phần đoàn tàu, toàn bộ **bộ luật giá** (những thứ đã biết chắc — **không được coi là tham số tự do**).
2. **Ước lượng riêng lẻ (partial):** $\theta, \rho_t, \varsigma_c$ từ hồi quy log–log trên bảng giá cào; $h_0(u)$ từ đường cong trả vé nếu có; $\bar\lambda_{\text{vùng}}$ từ tần suất bão lịch sử.
3. **SMM cho phần còn lại:** $\{\kappa, \alpha, \beta, \gamma_{\text{peak}}, w_m, a_m, b_m, \beta_{\text{cost}}, \mu_n, \dots\}$ khớp M1–M18. Dùng CMA-ES hoặc Bayesian Optimization; **common random numbers** để hàm mục tiêu trơn.

### 9.3. Định cỡ (sizing) — bài toán con hay toàn mạng?

Đề bài yêu cầu **"giai đoạn đầu thử nghiệm trên mác tàu, tuyến, loại chỗ và khung thời gian cụ thể"**. Khuyến nghị **2 tầng**:

| Bộ | Phạm vi | Quy mô ước tính |
|---|---|---|
| `pilot` | **SE1/SE2 + SE3/SE4 + SE19/20 + NA1/2**, 1 tuyến HN–SG, 3 loại chỗ, **01/2024–07/2026** (31 tháng) | ~1.900 chuyến/năm; ~231–595 O–D/chuyến; ~**8–12 triệu bản ghi log tìm kiếm**, ~**1,2 triệu vé**; ~3–6 GB parquet |
| `full` | 5 đôi Thống Nhất + toàn bộ khu đoạn + HN–HP + HN–LC | ~**40–60 triệu log**, ~**7–9 triệu vé/3 năm** (khớp với ~7,1 triệu lượt/năm của VNR) |

**Nguyên tắc:** sinh `full` để đúng hiện thực tổng thể, **chấm điểm trên `pilot`** để vòng lặp thực nghiệm nhanh.

---

## 10. Chỉ số đánh giá — định nghĩa toán học

### 10.1. Dự báo (dữ liệu ĐẾM, RẤT THƯA — chọn sai chỉ số là hỏng)

Ở mức $(r,\omega,c,u)$, phần lớn giá trị **bằng 0** ⇒ **MAPE không xác định, RMSE bị chi phối bởi vài ô lớn**. Dùng:

$$\mathrm{MASE} = \frac{\frac{1}{n}\sum_n |q_n - \hat q_n|}{\frac{1}{T-s}\sum_{t=s+1}^{T}|q_t - q_{t-s}|},\qquad s \in \{7,\ 364\}$$
$$D_{\text{Poisson}} = 2\sum_n \Big[q_n \ln\tfrac{q_n}{\hat\mu_n} - (q_n - \hat\mu_n)\Big] \quad (\text{quy ước } 0\ln 0 = 0)$$
$$\mathrm{PL}_\alpha(q,\hat q_\alpha) = \big(\alpha - \mathbb{1}[q < \hat q_\alpha]\big)\big(q - \hat q_\alpha\big); \qquad \mathrm{CRPS}(F,q) = \int_{\mathbb{R}} \big(F(z) - \mathbb{1}[z \ge q]\big)^2 dz$$

**Bắt buộc dự báo phân phối, không phải điểm.** Vì quyết định quota là bài toán newsvendor: mức bảo vệ tối ưu (Littlewood cho 2 hạng) là
$$\Pr\big(D_1 > y^\*\big) = \frac{f_2}{f_1} \;\Longrightarrow\; y^\* = F_1^{-1}\!\Big(1 - \tfrac{f_2}{f_1}\Big)$$
⇒ **cần lượng vị, không cần trung bình**. Một mô hình có MAE tốt nhưng đuôi sai sẽ cho quota tệ.

### 10.2. Nhất quán phân cấp — hòa giải MinT

Cấu trúc **cộng tính bắt buộc**:
$$x_e = \sum_\omega A_{e\omega}\, q_\omega, \qquad q_{r} = \sum_\omega q_{r\omega}$$
⇒ đây **đúng là một chuỗi thời gian phân nhóm (grouped time series)** với ma trận tổng $S = \begin{bmatrix} A \\ \mathbf{1}^\top \\ I \end{bmatrix}$.

Dự báo cơ sở $\hat{\mathbf{y}}$ (không nhất quán) → hòa giải:
$$\tilde{\mathbf{y}} = S\big(S^\top W^{-1} S\big)^{-1} S^\top W^{-1}\,\hat{\mathbf{y}}$$
với $W$ = ma trận hiệp phương sai sai số cơ sở (**MinT**, Wickramasuriya–Athanasopoulos–Hyndman 2019). Tính chất: phép chiếu này **không bao giờ làm xấu** sai số kỳ vọng so với dự báo cơ sở và đảm bảo $\hat x_e$ **cộng đúng** từ $\hat q_\omega$.

> ⚠️ Không hòa giải ⇒ dự báo O–D và dự báo tải khu gian mâu thuẫn ⇒ hệ ràng buộc $Ay \le C$ được nuôi bằng đầu vào tự mâu thuẫn ⇒ **quota vô nghĩa**. Đây là lỗi phổ biến nhất mà giám khảo có kinh nghiệm sẽ hỏi. **Đưa MinT vào kiến trúc = điểm cộng lớn.**

### 10.3. Doanh thu / khai thác

$$\text{Hệ số sử dụng chỗ theo khu gian: } \;\mathrm{LF}_e = \frac{x_e}{C_e};\qquad \text{Hệ số hk.km: } \;\mathrm{PKU} = \frac{\sum_e x_e \ell_e}{\sum_e C_e \ell_e}$$
> **PKU (passenger-km utilisation) mới là chỉ số đúng**, không phải "số vé bán/số chỗ". Bán 100 vé chặng 50 km ≠ bán 100 vé chặng 1.700 km. Đề bài đặt mục tiêu **+3–8% PKU** ⇒ mẫu số $\sum_e C_e \ell_e$ = **ghế-km cung ứng**.

$$\mathrm{RO} = \frac{Z^{\text{policy}} - Z^{\text{FCFS}}}{Z^{\text{opt}} - Z^{\text{FCFS}}};\qquad \text{Ghế rỗng cục bộ} = \sum_e (C_e - x_e)\,\ell_e$$
$$\text{Gap ratio} = \frac{\#\{\text{khoảng trống có } \ell \ge \ell_{\min}\}}{K};\qquad \text{Tỷ lệ đổi chỗ} = \frac{\#\{\text{vé có } M \ge 2\}}{\#\text{vé}}$$
$$\text{Chuyển đổi tìm kiếm} = \frac{\#\text{giao dịch}}{\#\text{yêu cầu}};\qquad \text{Cầu chưa đáp ứng} = \frac{\#\{\text{từ chối vì hết chỗ}\}}{\#\text{yêu cầu}}$$

### 10.4. Công bằng giá — kiểm định thống kê, không phải cam kết

$$\mathrm{CV}_p(\omega,c) = \frac{\mathrm{sd}_u\big[p(u)\big]}{\mathbb{E}_u\big[p(u)\big]} \le \overline{\mathrm{CV}}; \qquad \text{Gini}(\text{mức giảm}) \le \overline{G}$$
$$H_0:\;\; \mathbb{E}\big[p \mid Z = z\big] = \mathbb{E}\big[p\big] \;\;\forall z \in \{\text{giới tính, tuổi, tần suất tìm kiếm, thiết bị}\}$$
Kiểm định bằng permutation test hoặc hồi quy $p \sim Z$ + kiểm định $F$ chung. **Bắt buộc không bác bỏ $H_0$.**
$$\text{Vi phạm chính sách} = \#\{p < \underline F\} + \#\{p > \overline F\} + \#\{\text{đối tượng CSXH không được giảm đúng}\} \;\overset{!}{=}\; 0$$

### 10.5. Tốc độ

$$T_{\text{recalc}} = \text{thời gian tính lại bid price + quota cho 1 chuyến khi có 1 sự kiện (mua/trả)}$$
Mục tiêu: **p95 < 200 ms** (đủ cho "near real-time" của hệ thống bán vé). Nhờ Định lý 1, cận này khả thi.

---

## 11. Bảng tổng hợp tham số (trỏ tới file cấu hình)

Toàn bộ tham số số học nằm ở **`04_THAM_SO_CAU_HINH_MO_PHONG.yaml`** để đảm bảo:
- **Tái lập được (reproducible)**: một seed + một file YAML ⇒ một dataset duy nhất.
- **Kiểm toán được**: hash của YAML được ghi vào metadata mỗi file parquet.
- **Phân tích độ nhạy**: quét $\vartheta$ theo lưới/Sobol để báo cáo độ nhạy của kết luận.

---

## 12. Bốn sai lầm toán học sẽ khiến bài thi mất điểm (và cách tránh)

| Sai lầm | Vì sao chết | Cách đúng |
|---|---|---|
| **Sinh vé trực tiếp** từ một phân phối khớp với số liệu quan sát | Đã "nướng" sẵn hiệu ứng của chính sách cũ vào dữ liệu ⇒ AI không thể vượt được chính sách cũ, vì mọi phản thực (counterfactual) đều không tồn tại | Sinh **cầu tiềm ẩn** ⇒ cho **chính sách** tác động lên nó ⇒ vé là **đầu ra**, không phải đầu vào |
| **Giá không vào tiện ích** | Mọi thuật toán pricing cho kết quả như nhau ⇒ bài toán rỗng | Nested logit với $\beta_p > 0$, hiệu chuẩn độ co giãn theo cự ly |
| **Bỏ log tìm kiếm bị từ chối** | Cầu bị kiểm duyệt ⇒ dự báo thiên lệch **xuống** đúng ở nơi cần nhất (chặng cháy vé) | Log toàn bộ yêu cầu + lưu $\Lambda$ thật ở `_ground_truth/` để chấm điểm unconstraining |
| **Ràng buộc chính sách xã hội là "phạt mềm"** | Vi phạm pháp luật; đề bài yêu cầu **0 vi phạm** | Ràng buộc cứng + kiểm toán tự động; `max` không `∏`; giảm CSXH **sau** giảm động |

---

## 13. Tham chiếu học thuật

- Talluri, K. & van Ryzin, G. (2004). *The Theory and Practice of Revenue Management* — DLP, bid price, network RM, Littlewood.
- Schrijver, A. (1998). *Theory of Linear and Integer Programming* — tính TU của ma trận khoảng / consecutive-ones.
- Golumbic, M. (2004). *Algorithmic Graph Theory and Perfect Graphs* — đồ thị khoảng, $\chi = \omega$.
- Kierstead, H. & Trotter, W. (1981). *An extremal problem in recursive combinatorics* — tô màu khoảng trực tuyến, cận $3\omega-2$.
- Wickramasuriya, S., Athanasopoulos, G., Hyndman, R. (2019). *Optimal forecast reconciliation... (MinT)*, JASA.
- Train, K. (2009). *Discrete Choice Methods with Simulation* — nested logit, điều kiện $0<\mu\le1$.
- McFadden, D. (1989). *A method of simulated moments...*, Econometrica.
- Chernozhukov et al. (2018). *Double/Debiased Machine Learning* — ước lượng hiệu ứng nhân quả của giá khi có nội sinh.
