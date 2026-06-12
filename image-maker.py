import shlex

from PIL import Image


class Reference:
    """変数の参照渡しを実現するためのラップクラス"""

    def __init__(self, name, variables):
        self.name = name
        self.variables = variables

    def get(self):
        if self.name not in self.variables:
            raise ValueError(f"未定義の変数への参照です: {self.name}")
        return self.variables[self.name]

    def set(self, value):
        self.variables[self.name] = value


class ScriptEngine:
    def __init__(self):
        self.variables = {}
        self.commands = {}
        self._register_builtins()

    def register(self, cmd_name):
        """新しいコマンドを登録するためのデコレータ"""

        def decorator(func):
            self.commands[cmd_name] = func
            return func

        return decorator

    def _register_builtins(self):
        """必須の組み込みコマンドを登録"""

        @self.register("load")
        def cmd_load(img_ref, path):
            if not isinstance(img_ref, Reference):
                raise ValueError(
                    "loadコマンドの第1引数は参照渡し(&変数名)で指定します"
                )

            # 画像を読み込んで、参照先の変数にセット
            img = Image.open(path)
            img_ref.set(img)
            print(f"[Engine] 画像を読み込みました: {path} -> &{img_ref.name}")

        @self.register("save")
        def cmd_save(img, path):
            # もし誤って参照渡しされた場合は実体を取得
            if isinstance(img, Reference):
                img = img.get()

            if not isinstance(img, Image.Image):
                raise ValueError(
                    "saveコマンドの第1引数はImageオブジェクトを指定します"
                )

            img.save(path)
            print(f"[Engine] 画像を保存しました: {path}")

    def _parse_arg(self, arg):
        """引数の型を解析してPythonのオブジェクトに変換"""
        # 1. 参照渡し (&変数名)
        if arg.startswith("&"):
            return Reference(arg[1:], self.variables)

        # 2. 文字列リテラル ("text" または 'text')
        if (arg.startswith('"') and arg.endswith('"')) or (
            arg.startswith("'") and arg.endswith("'")
        ):
            return arg[1:-1]

        # 3. 数値リテラル
        try:
            return int(arg)
        except ValueError:
            pass
        try:
            return float(arg)
        except ValueError:
            pass

        # 4. 変数
        if arg in self.variables:
            return self.variables[arg]

        raise ValueError(f"未定義の変数または不正な値です: {arg}")

    def execute(self, script_text):
        """スクリプトを1行ずつ評価して実行"""
        for line_num, line in enumerate(script_text.strip().split("\n"), 1):
            line = line.strip()

            # 空行とコメントをスキップ
            if not line or line.startswith("#"):
                continue

            try:
                # 代入文の処理 (変数 = 計算式)
                if "=" in line and not line.startswith("="):
                    left, right = [part.strip() for part in line.split("=", 1)]

                    # スクリプト内で許可する安全な組み込み関数
                    allowed_funcs = {
                        "int": int,
                        "float": float,
                        "str": str,
                        "round": round,
                        "abs": abs,
                        "len": len,
                    }

                    # 変数と許可した関数を合わせた環境を作成
                    eval_env = {**self.variables, **allowed_funcs}

                    # __builtins__ を空にして危険な関数を弾きつつ、許可した関数と変数のみを使えるようにする
                    self.variables[left] = eval(right, {"__builtins__": {}}, eval_env)
                    continue

                # コマンドの処理
                # posix=Falseにすることでクォートを保持したままトークン分割
                tokens = shlex.split(line, posix=False)
                cmd_name = tokens[0]
                args = [self._parse_arg(t) for t in tokens[1:]]

                if cmd_name in self.commands:
                    self.commands[cmd_name](*args)
                else:
                    raise ValueError(f"未知のコマンドです: {cmd_name}")

            except Exception as e:
                print(f"実行エラー (行 {line_num}) [{line}] -> {e}")


# ==========================================
# カスタムコマンドの追加テンプレート
# ==========================================
engine = ScriptEngine()


# 例: 参照渡しの変数を書き換えるコマンド（画像をリサイズして変数を上書きする）
@engine.register("resize-self")
def cmd_resize_self(img_ref, width, height):
    if not isinstance(img_ref, Reference):
        raise ValueError("resize-selfの第1引数は参照(&変数)で指定します")

    img = img_ref.get()  # 現在の画像を取得
    resized_img = img.resize((width, height))
    img_ref.set(resized_img)  # 参照元の変数を上書き
    print(f"[Engine] 画像を {width}x{height} にリサイズしました")


# 例: 単純な出力コマンド
@engine.register("echo")
def cmd_echo(*args):
    # Referenceオブジェクトが混ざっていたら値を取り出す
    vals = [a.get() if isinstance(a, Reference) else a for a in args]
    print("echo>", *vals)


# ==========================================
# 実行テスト
# ==========================================
if __name__ == "__main__":
    import os
    import pathlib
    import sys

    if len(sys.argv) < 2:
        myname = os.path.basename(__file__)
        print(f"Usage: python {myname} <script-file>")
        exit(0)

    script_path = pathlib.Path(sys.argv[1])
    script_text = script_path.read_text(encoding="utf-8")
    engine.execute(script_text)
