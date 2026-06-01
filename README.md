# SHAPE-MaP Local Runner

**English summary:** A local web interface for demultiplexing SHAPE-MaP sequencing reads and running ShapeMapper2 under Windows + WSL. The tool keeps FASTQ/FASTA data on the local machine and provides a browser UI at `http://127.0.0.1:8765`.

本项目是一个本地运行的 SHAPE-MaP 分析工具。它提供一个浏览器网页界面，用于上传或选择本地 FASTQ/FASTA 文件，按 barcode/引物拆分 mixed reads，并调用 WSL Ubuntu 中的 ShapeMapper2 完成 SHAPE-MaP 分析。
<img width="1983" height="793" alt="image" src="https://github.com/user-attachments/assets/aa813697-6a27-4d49-9947-631381003739" />


数据不会上传到互联网。网页运行在本机：

```text
http://127.0.0.1:8765
```

## Quick Start

This project is designed for Windows + WSL. ShapeMapper2 itself is installed separately inside WSL.

```powershell
# 1. Install ShapeMapper2 after downloading shapemapper2-2.3.tar.gz into downloads/
powershell -ExecutionPolicy Bypass -File .\scripts\install_shapemapper2.ps1

# 2. Check ShapeMapper2
powershell -ExecutionPolicy Bypass -File .\scripts\check_shapemapper2.ps1

# 3. Start the local web UI
powershell -ExecutionPolicy Bypass -File .\scripts\start_local_web.ps1
```

Then open:

```text
http://127.0.0.1:8765
```

## Citation

If you use this repository in academic work, please cite this software repository and the underlying ShapeMapper2/SHAPE-MaP publications. See [CITATION.cff](CITATION.cff).

## License

This project is released under the MIT License. See [LICENSE](LICENSE).

## 功能

- 本地 HTML 入口页
- 本地网页分析界面
- mixed FASTQ 按 barcode 拆分为：
  - modified
  - untreated
  - denatured
- 支持 single-end 和 paired-end FASTQ
- 支持完整参考 FASTA
- 支持多个参考片段 FASTA 拼接成完整 target
- 支持 tiled amplicon 的 ShapeMapper2 primers 文件
- 自动调用 ShapeMapper2 v2.3
- 网页端显示运行日志、拆分统计、失败原因和建议

## 推荐运行环境

### 操作系统

- Windows 10/11
- WSL2
- Ubuntu

### 必需软件

Windows 侧：

- PowerShell
- WSL
- 浏览器，例如 Edge/Chrome

WSL Ubuntu 侧：

- Python 3
- ShapeMapper2 v2.3

### Linux-only usage

The current launch scripts are optimized for Windows + WSL. On a pure Linux machine, you can run the Python entry points directly:

```bash
python3 scripts/web_app.py --port 8765
python3 scripts/shape_map_local.py templates/project.example.json --demux-only
```

For full ShapeMapper2 analysis on Linux, install ShapeMapper2 and update the `shapemapper.executable` field in your project JSON if needed.

## 硬件要求

硬件需求主要取决于 FASTQ 文件大小、参考序列长度、amplicon 数量以及是否同时跑多个项目。ShapeMapper2 官方流程会产生中间文件，本项目还会先拆分 mixed FASTQ，所以硬盘空间要预留得比原始数据更大。

### 最低配置

适合小 RNA、少量 amplicon、测试数据或预分析：

```text
CPU：4 核
内存：8 GB
可用硬盘：原始 FASTQ 总大小的 3-5 倍
```

例如原始 R1/R2 加起来 5 GB，建议至少预留 15-25 GB 可用空间。

### 推荐配置

适合常规 SHAPE-MaP 项目、paired-end 数据、多个 300 bp tiled amplicons：

```text
CPU：8 核或以上
内存：16-32 GB
可用硬盘：原始 FASTQ 总大小的 5-8 倍
```

如果原始数据 20 GB，建议预留 100 GB 左右空间，会比较稳。

### 大数据配置

适合很多样本、长 RNA、病毒基因组、大量 tiled amplicons 或反复调参数：

```text
CPU：12-24 核
内存：32-64 GB
可用硬盘：200 GB 以上，最好使用 SSD
```

### CPU 核心数怎么设置

网页里的 `nproc` 对应 ShapeMapper2 的并行线程数。一般建议：

```text
4 核电脑：nproc = 2 或 3
8 核电脑：nproc = 4 或 6
12 核电脑：nproc = 8
16 核以上：nproc = 8-12
```

不要把所有核心都分给分析程序，Windows、WSL 和浏览器也需要资源。比如 8 核电脑设成 `8` 可以跑，但电脑会明显卡；设成 `4` 或 `6` 通常更舒服。

### 内存注意事项

常规 amplicon 数据通常 16 GB 内存够用。  
如果参考序列很长、reads 很多、使用 STAR aligner 或同时运行多个项目，建议 32 GB 或更高。

### 硬盘空间注意事项

本项目会占用几类空间：

- 原始 FASTQ
- 拆分后的 modified / untreated / denatured FASTQ
- ShapeMapper2 输出结果
- ShapeMapper2 临时目录
- 网页上传文件副本

ShapeMapper2 临时目录在 WSL 原生目录：

```text
~/shape_map_runs/<project_name>/temp
```

项目结果目录在 Windows project 中：

```text
results/<project_name>/
```

如果磁盘空间不足，优先清理：

```text
results/<旧项目名>/
data/web_uploads/
```

确认不再需要后，也可以清理 WSL 中的临时目录：

```bash
rm -rf ~/shape_map_runs/<旧项目名>
```

ShapeMapper2 安装在 WSL 用户目录：

```text
~/tools/shapemapper2-2.3
```

版本检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_shapemapper2.ps1
```

正常输出应类似：

```text
ShapeMapper v2.3.0
```

## 新电脑部署步骤

### 1. 安装 WSL Ubuntu

在 Windows PowerShell 中运行：

```powershell
wsl --install
```

安装完成后打开 Ubuntu，创建用户名。

检查 WSL 是否可用：

```powershell
wsl --exec bash -lc "whoami; uname -a"
```

### 2. 准备项目目录

将整个项目文件夹复制到新电脑，例如：

```text
C:\Users\<你的用户名>\Documents\shape-map-local-runner
```

建议保留以下目录结构：

```text
shape-map-local-runner/
  README.md
  SHAPE-MaP-Local-Runner.html
  start_shape_map_web.bat
  scripts/
  templates/
  data/
  projects/
  results/
  downloads/
```

### 3. 安装 ShapeMapper2

从 GitHub 下载 ShapeMapper2 release：

```text
https://github.com/Weeks-UNC/shapemapper2/releases/download/v2.3/shapemapper2-2.3.tar.gz
```

将文件放到：

```text
downloads/shapemapper2-2.3.tar.gz
```

然后在项目目录中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_shapemapper2.ps1
```

这个脚本会自动把 Windows 路径转换成 WSL 路径，并将 ShapeMapper2 解压到：

```text
~/tools/shapemapper2-2.3
```

验证：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_shapemapper2.ps1
```

## 启动网页

方式一：双击

```text
start_shape_map_web.bat
```

然后打开：

```text
SHAPE-MaP-Local-Runner.html
```

方式二：PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local_web.ps1
```

浏览器访问：

```text
http://127.0.0.1:8765
```

注意：启动服务的 PowerShell 窗口需要保持打开。关闭窗口后，本地网页服务会停止。

## 输入文件

### FASTQ

支持：

```text
.fastq
.fq
.fastq.gz
.fq.gz
```

paired-end 数据需要提供：

```text
R1
R2
```

建议大文件放在：

```text
data/raw/
```

网页中填写相对路径，例如：

```text
../data/raw/sample_R1.fq.gz
../data/raw/sample_R2.fq.gz
```

### 参考序列 FASTA

ShapeMapper2 需要 target FASTA。

要求：

- 使用 DNA 字母：`A/T/C/G`
- RNA 中的 `U` 应写成 `T`
- FASTA header 不要有复杂空格

示例：

```fasta
>target_5S
GCTTACGGCCATACCACCCTGAACGCGCCCGATCTCGTCTGATCTCGGAAGCTAAGCAGGGTCGGGCCTGGTTAGTACTTGGATGGGAGACCGCCTGGGAATACCGGGTGCTGTAGGCTT
```

### 参考片段拼接

如果因为序列较长而设计了多个约 300 bp tiled amplicons，可以上传多个片段 FASTA，程序会按顺序和重叠区域拼接成完整参考序列。

片段 FASTA 示例：

```fasta
>fragment_001
AAACCCGGGTTTAAACCC
>fragment_002
TTTAAACCCGGGAAATTT
>fragment_003
GGGAAATTTCCCGGGAAA
```

如果网页中填写了片段顺序，应与 FASTA header 一致：

```text
fragment_001
fragment_002
fragment_003
```

### ShapeMapper2 primers 文件

这个文件不是 SnapGene `.dna` 文件，而是纯文本 `.txt`。

用于 tiled amplicon，让 ShapeMapper2 知道每对扩增引物。

格式：

```text
forward_primer_1 reverse_primer_1
forward_primer_2 reverse_primer_2
forward_primer_3 reverse_primer_3
```

多 target 格式：

```text
>target_1
forward_primer_1 reverse_primer_1
forward_primer_2 reverse_primer_2

>target_2
forward_primer_1 reverse_primer_1
```

## Barcode 拆分参数建议

如果 barcode 很短，例如 6-8 bp，并且在 read 5' 端：

```text
搜索 read 前多少 bp：8 或 10
允许错配数：0
只允许在 read 开头匹配：勾选
同时检查反向互补序列：不勾选
```

如果 barcode 前面还有 UMI/random bases：

```text
搜索 read 前多少 bp：12-20
允许错配数：0
只允许在 read 开头匹配：不勾选
```

如果不确定 barcode 在 R1 还是 R2，可以先只运行“只按引物拆分样本”，查看网页端拆分结果。

## ShapeMapper2 参数建议

默认建议：

```text
min-depth: 1000
min-mapq: 10
max-bg: 0.05
nproc: 4
amplicon: 勾选
```

更严格的正式分析可以将：

```text
min-depth: 2000
```

如果数据非常深，可以使用：

```text
min-depth: 5000
```

## 输出目录

每个项目输出在：

```text
results/<project_name>/
```

主要文件：

```text
results/<project_name>/demux/
results/<project_name>/demux/demux_summary.json
results/<project_name>/shapemapper/
results/<project_name>/run_summary.json
results/web_logs/
```

`demux_summary.json` 会记录：

- total reads
- unmatched reads
- ambiguous reads
- modified reads
- untreated reads
- denatured reads

网页端也会显示这些统计。

## 常见问题

### 1. 打开分析网页按钮一直是灰色

原因通常是本地服务没有启动。

先运行：

```text
start_shape_map_web.bat
```

然后刷新：

```text
SHAPE-MaP-Local-Runner.html
```

或者直接访问：

```text
http://127.0.0.1:8765
```

### 2. 找不到 FASTQ 文件

检查路径不要带引号。

推荐使用相对路径：

```text
../data/raw/sample_R1.fq.gz
```

Windows 绝对路径也可以，但不要写成：

```text
"C:\Users\...\sample_R1.fq.gz"
```

### 3. modified 有 reads，但 untreated/denatured 为 0

通常说明：

- barcode 填错
- barcode 不在当前 FASTQ 文件中
- barcode 在 R2 而不是 R1
- barcode 方向相反
- 公司已经按 index 拆过样本，当前 FASTQ 不是 mixed 总文件

建议先运行：

```text
只按引物拆分样本
```

不要直接跑完整 ShapeMapper2。

### 4. ShapeMapper2 报 Operation not supported

这是 WSL 在 Windows 挂载目录中创建 Linux FIFO 管道失败。

本项目已将 ShapeMapper2 临时目录设置到 WSL 原生目录：

```text
~/shape_map_runs/<project_name>/temp
```

如果仍然出现，请确认正在使用最新脚本。

### 5. SnapGene `.dna` 文件能不能直接用

当前版本不直接读取 SnapGene `.dna`。

请从 SnapGene 导出：

- FASTA：作为参考序列
- 引物文本：作为 ShapeMapper2 primers 文件

## 项目脚本说明

```text
scripts/check_shapemapper2.ps1
```

检查 ShapeMapper2 是否安装成功。

```text
scripts/start_local_web.ps1
```

启动本地网页服务。

```text
scripts/install_shapemapper2.ps1
```

将 `downloads/shapemapper2-2.3.tar.gz` 安装到 WSL 的 `~/tools` 目录。

```text
scripts/web_app.py
```

本地网页后端。

```text
scripts/shape_map_local.py
```

核心 pipeline：参考拼接、FASTQ 拆分、调用 ShapeMapper2。

```text
scripts/scan_barcodes.py
```

扫描 R1/R2 中 barcode 的位置和方向。

## 迁移到新电脑的最小清单

必须复制：

```text
README.md
SHAPE-MaP-Local-Runner.html
start_shape_map_web.bat
scripts/
templates/
```

建议复制：

```text
projects/
data/
results/
downloads/shapemapper2-2.3.tar.gz
```

如果只迁移程序，不迁移旧数据，可以不复制 `results/`。  
如果不复制 `downloads/shapemapper2-2.3.tar.gz`，新电脑需要重新从 ShapeMapper2 GitHub release 下载。

## 数据安全

本项目默认只在本机运行：

```text
127.0.0.1
```

数据文件不会上传到云端。所有 FASTQ、FASTA、配置和结果都保存在本地 project 目录或 WSL 本机目录中。
