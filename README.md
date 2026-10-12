# AssemblyViewer:組裝動畫檢視器產生工具

把「STL 資料夾 + parts.csv」自動合成單一 HTML 檢視器,換案例只要換資料。

## 資料夾結構

```
AssemblyViewer/
├── build.py              建置腳本(只用標準函式庫)
├── template.html         固定範本:檢視器的 HTML/CSS/JS 都在這裡
├── vendor/
│   └── three.min.js      three.js 函式庫,所有專案共用,建置時自動內嵌,不用手動處理
├── README.md
└── projects/
    └── RockyRoller/      一個案例一個資料夾
        ├── stl/          從 CAD 匯出的零件 STL
        ├── parts.csv     零件與步驟資料
        └── project.json  專案名稱、機密標示、單位等設定
```

## 使用方式

```
python build.py projects/RockyRoller
```

輸出會放在該專案資料夾內(檔名見 project.json 的 output)。

## 新增案例

1. 複製 `projects/RockyRoller` 改名
2. 換掉 `stl/` 裡的 STL,改寫 `parts.csv`,調整 `project.json`
3. 執行 `python build.py projects/新案例`

## 零件表:parts.xlsx(優先)或 parts.csv

專案資料夾裡有 `parts.xlsx` 就讀它,沒有才讀 `parts.csv`(兩個都有時以 xlsx 為準)。
建議用 xlsx:`color` 欄有下拉選單,點儲存格選顏色,儲存格會自動顯示對應底色。
工作表 `parts` 必須是第一個工作表,第 1 列是欄位名稱。`build.py` 讀 xlsx 不需安裝任何套件。

## parts 欄位(xlsx / csv 相同)

| 欄位 | 說明 | 必填 |
|---|---|---|
| step | 第幾步組裝(整數) | 是 |
| stl_file | 對應的 STL 檔名 | 是 |
| part_name | 零件名稱 | 是 |
| pn | 料號;留空則用檔名 | 否 |
| qty | 數量 | 否 |
| explode_dir | x / y / z / -x / -y / -z;留空由檢視器自動決定 | 否 |
| explode_dist | 飛入距離(零件從多遠的地方飛進來裝上) | 否 |
| delay | 動畫延遲;留空依 step 自動排 | 否 |
| tool | 使用工具 | 否 |
| torque | 扭力 | 否 |
| note | 注意事項 | 否 |
| color | 零件顏色,直接填名稱(紅、橘、黃、綠、藍、淺藍、藍灰、紫、粉紅、棕、金、銀、白、淺灰、灰、深灰、黑,英文 red、blue 等也可);留空用預設藍灰色 | 否 |

存檔時用 UTF-8(Excel 的「CSV UTF-8」即可)。

## project.json

| 欄位 | 說明 |
|---|---|
| project_name | 顯示用專案名稱 |
| confidential | 機密標示文字,留空則不顯示 |
| unit | STL 單位,預設 mm |
| up_axis | 上方向,預設 Z |
| version | 版本號,會顯示在輸出中 |
| output | (已停用)輸出檔名固定為「資料夾名稱_viewer.html」 |

## 目前狀態

- **build.py**:已可檢查資料、內嵌 STL、自動內嵌 `vendor/three.min.js`、注入範本、輸出 HTML。
- **template.html**:已是一份可運作的基礎版檢視器(因原始檔案遺失,重新寫的,不是原本那份的程式碼)。這是**逐步組裝動畫,不是爆炸圖**:一開始畫面是空的,零件依 `step` 由小到大,一個一個從某個方向飛進來定位,裝上去之後就留在畫面上,直到全部裝完。具備:
  - 依 `step` 依序播放組裝動畫,`delay` 欄可讓某一步等待更久才開始
  - `explode_dir` / `explode_dist` 這兩欄沿用原本欄位名稱,但意義是「這個零件從哪個方向、多遠的地方飛進來裝上」,不是往外爆炸
  - 播放 / 暫停、拖曳進度條(scrub)
  - 「轉向當前零件」(預設勾選):播放或拖曳進度條時,相機會平滑轉到零件飛入的那一側,並拉近成斜 3/4 視角,讓正在組裝的零件在前方、朝著已裝好的組件飛入;手動拖曳視角後暫停,換下一步再自動轉;全部裝完後拉回全景。視角可在 template.html 的 VIEW_YAW(側轉角)、VIEW_ELEV(抬高角)、followDist(距離)調整
  - 自動旋轉開關,滑鼠拖曳也可手動轉視角
  - 點擊零件表格的列,會在 3D 畫面反白對應零件
  - 沒有填 `explode_dir` / `explode_dist` 時,會自動用「零件中心相對組裝中心的方向」估算飛入方向與距離
  - 偵測瀏覽器不支援 WebGL 時顯示替代訊息
- **待辦(下一步)**:
  - 對照原始檢視器(如果找得回來)或實際組裝順序,校正各零件的飛入方向、距離、動畫時間,目前的數值多半是自動估算或預設值
  - 點選零件顯示 P/N 的資訊卡(目前只有反白,還沒有彈出詳細資訊)
  - 平移功能
  - STL 簡化面數(零件多時檔案會變大,可視情況做)
  - 逐步模式的說明文字目前已經在零件表裡(工具/扭力/注意事項欄),但還沒有「上一步/下一步」的獨立導覽按鈕,可視需要再加
