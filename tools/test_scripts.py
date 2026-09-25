"""Tests for scripts/*.ps1 against local fixtures: no internet, no real engine, no audio devices.

    python tools\\test_scripts.py

Each test copies scripts/, config/ and vcgui/ into a temp "repo" and points the manifests at a
local HTTP server (with Range support, for curl -C -). Needs Windows PowerShell 5.1; the 7-Zip
and FFmpeg tests are skipped when those tools are missing.
"""

import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEVEN_ZIP = next((p for p in (os.path.join(os.environ.get("PROGRAMW6432", ""), "7-Zip", "7z.exe"),
                              os.path.join(os.environ.get("PROGRAMFILES", ""), "7-Zip", "7z.exe"))
                  if os.path.isfile(p)), shutil.which("7z"))
FFMPEG = shutil.which("ffmpeg")
GUI_WITH_ANCHORS = ('if __name__ == "__main__":\n    import FreeSimpleGUI as sg\n    sg.Window("RVC - GUI", layout)\n'
                    '    key="im"\n    key="vc"\n    elif event in ["vc", "im"]:\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w", encoding=None if isinstance(data, bytes) else "utf-8") as f:
        f.write(data)


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


class RangeHandler(http.server.BaseHTTPRequestHandler):
    """Serves Server.files {url path: bytes}; paths in Server.flaky send half the body once, then drop."""

    def do_GET(self):
        data = self.server.files.get(self.path)
        if data is None:
            self.send_error(404)
            return
        m = re.match(r"bytes=(\d+)-", self.headers.get("Range", ""))
        start = int(m.group(1)) if m else 0
        if m and start >= len(data):
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{len(data)}")
            self.end_headers()
            return
        self.send_response(206 if m else 200)
        if m:
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        self.send_header("Content-Length", str(len(data) - start))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        body = data[start:]
        if self.path in self.server.flaky:
            self.server.flaky.discard(self.path)
            self.wfile.write(body[: len(body) // 2])
            self.wfile.flush()
            self.connection.shutdown(2)  # connection drops mid-download
            return
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class ScriptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
        cls.server.files, cls.server.flaky = {}, set()
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gvc-scripts-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.make_repo("repo")

    def make_repo(self, name):
        repo = os.path.join(self.tmp, name)
        for d in ("scripts", "config", "vcgui"):
            shutil.copytree(os.path.join(REPO, d), os.path.join(repo, d))
        return repo

    def ps(self, script, *args, repo=None):
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               os.path.join(repo or self.repo, "scripts", script), *args]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return p.returncode, p.stdout + p.stderr

    def ps_command(self, command):
        p = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                           capture_output=True, text=True, timeout=300)
        return p.returncode, p.stdout + p.stderr


# ---------------------------------------------------------------- get-models.ps1


class GetModelsTest(ScriptTest):
    def setUp(self):
        super().setUp()
        self.blobs, voices = {}, []
        for vid, default in (("v1", True), ("v2", True), ("v3", False)):
            files = []
            for kind, ext, optional, n in (("rvc-pth", "pth", False, 300_000), ("rvc-index", "index", False, 500_000),
                                           ("beatrice", "zip", True, 100_000)):
                data = os.urandom(n)
                remote, local = f"F/{vid}/{vid}.{ext}", f"models/{vid}/{vid}.{ext}"
                self.server.files[f"/rev1/{remote}"] = data
                self.blobs[local] = data
                entry = {"kind": kind, "remote": remote, "local": local, "size": n, "sha256": sha(data)}
                if optional:
                    entry["optional"] = True
                files.append(entry)
            voices.append({"id": vid, "label": "Voice " + vid, "default": default, "files": files})
        manifest = {"source": "test", "revision": "rev1", "url_template": self.base + "/{revision}/{remote}",
                    "license": "test", "attribution": "Test attribution line.", "voices": voices}
        write(os.path.join(self.repo, "config", "models.json"), json.dumps(manifest))

    def path(self, local):
        return os.path.join(self.repo, *local.split("/"))

    def test_default_voices_resume_and_rerun(self):
        write(self.path("models/v1/v1.index"), self.blobs["models/v1/v1.index"][:123_456])  # partial at final path
        code, out = self.ps("get-models.ps1")
        self.assertEqual(code, 0, out)
        self.assertIn("Resuming v1.index", out)
        self.assertEqual(sorted(os.listdir(os.path.join(self.repo, "models"))), ["v1", "v2"])
        self.assertFalse(os.path.exists(self.path("models/v1/v1.zip")))  # optional
        for local in ("models/v1/v1.pth", "models/v1/v1.index", "models/v2/v2.pth", "models/v2/v2.index"):
            self.assertEqual(read_bytes(self.path(local)), self.blobs[local])
        self.assertIn("Test attribution line.", out)
        code, out = self.ps("get-models.ps1")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("already verified"), 4)
        self.assertNotIn("Downloading", out)

    def test_voice_list_with_commas_and_beatrice(self):
        code, out = self.ps("get-models.ps1", "-Voice", "v3,v1", "-IncludeBeatrice")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(self.path("models/v3/v3.zip")))
        self.assertTrue(os.path.exists(self.path("models/v1/v1.zip")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "models", "v2")))

    def test_interrupted_download_never_leaves_a_final_file(self):
        self.server.flaky.add("/rev1/F/v2/v2.index")
        code, out = self.ps("get-models.ps1", "-Voice", "v2")
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(self.path("models/v2/v2.index")))  # launch.ps1 still says "missing"
        self.assertTrue(os.path.exists(self.path("models/v2/v2.index.part")))
        code, out = self.ps("get-models.ps1", "-Voice", "v2")
        self.assertEqual(code, 0, out)
        self.assertIn("Resuming v2.index", out)
        self.assertEqual(read_bytes(self.path("models/v2/v2.index")), self.blobs["models/v2/v2.index"])
        self.assertFalse(os.path.exists(self.path("models/v2/v2.index.part")))

    def test_corrupt_part_is_deleted_and_redownloaded(self):
        write(self.path("models/v1/v1.pth.part"), os.urandom(300_000))  # full size, wrong bytes
        code, out = self.ps("get-models.ps1", "-Voice", "v1")
        self.assertEqual(code, 1, out)
        self.assertIn("was corrupt", out)
        self.assertFalse(os.path.exists(self.path("models/v1/v1.pth.part")))
        code, out = self.ps("get-models.ps1", "-Voice", "v1")
        self.assertEqual(code, 0, out)
        self.assertEqual(read_bytes(self.path("models/v1/v1.pth")), self.blobs["models/v1/v1.pth"])

    def test_bad_complete_or_oversized_files_are_refused(self):
        bad = bytearray(self.blobs["models/v2/v2.pth"])
        bad[0] ^= 0xFF
        write(self.path("models/v2/v2.pth"), bytes(bad))
        code, out = self.ps("get-models.ps1", "-Voice", "v2")
        self.assertEqual(code, 1, out)
        self.assertIn("SHA256 is", out)
        self.assertIn("Delete it", out)
        write(self.path("models/v2/v2.pth"), self.blobs["models/v2/v2.pth"] + b"x")
        code, out = self.ps("get-models.ps1", "-Voice", "v2")
        self.assertEqual(code, 1, out)
        self.assertIn("larger than expected", out)

    def test_unknown_voice_and_list(self):
        code, out = self.ps("get-models.ps1", "-Voice", "nope")
        self.assertEqual(code, 1, out)
        self.assertIn("Unknown voice id(s): nope", out)
        self.assertIn("v1, v2, v3", out)
        code, out = self.ps("get-models.ps1", "-List")
        self.assertEqual(code, 0, out)
        self.assertIn("(default)", out)


# ---------------------------------------------------------------- install-engine.ps1


@unittest.skipUnless(SEVEN_ZIP, "7-Zip is needed to build the fixture archives")
class InstallEngineTest(ScriptTest):
    def make_archive(self, name, gui_text=GUI_WITH_ANCHORS, top="RVC20260718Nvidia", extra=None):
        src = os.path.join(self.tmp, "src-" + name)
        pkg = os.path.join(src, *top.split("/"))
        files = {"go-realtime_gui.bat": "@echo off\r\n", "runtime/python.exe": "", "configs/config.py": "",
                 "assets/hubert_base/config.json": "{}", "assets/hubert_base/pytorch_model.bin": "x",
                 "assets/rmvpe/rmvpe.pt": "x", "realtime_gui.py": gui_text}
        files.update(extra or {})
        for rel, text in files.items():
            write(os.path.join(pkg, *rel.split("/")), text)
        archive = os.path.join(self.tmp, name + ".7z")
        subprocess.run([SEVEN_ZIP, "a", "-bso0", "-bsp0", archive, os.path.join(src, top.split("/")[0])], check=True)
        return read_bytes(archive)

    def use_archive(self, data, sha_override=None, repo=None):
        self.server.files["/engine.7z"] = data
        with open(os.path.join(REPO, "config", "engine.lock.json"), encoding="utf-8") as f:
            lock = json.load(f)
        lock.update(url=self.base + "/engine.7z", size=len(data), sha256=sha_override or sha(data))
        write(os.path.join(repo or self.repo, "config", "engine.lock.json"), json.dumps(lock))

    def downloads(self, *parts):
        return os.path.join(self.repo, "downloads", *parts)

    def test_resume_verify_extract_and_rerun(self):
        data = self.make_archive("good")
        self.use_archive(data)
        write(self.downloads("RVC20260718Nvidia.7z"), data[: len(data) // 3])  # partial at the final name
        code, out = self.ps("install-engine.ps1")
        self.assertEqual(code, 0, out)
        self.assertIn("Resuming RVC20260718Nvidia.7z", out)
        self.assertIn("SHA256 OK", out)
        self.assertIn("Engine check passed", out)
        engine = os.path.join(self.repo, "engine")
        self.assertTrue(os.path.isfile(os.path.join(engine, "runtime", "python.exe")))
        self.assertFalse(os.path.exists(self.downloads("_extract")))
        self.assertEqual(read_bytes(self.downloads("RVC20260718Nvidia.7z")), data)
        code, out = self.ps("install-engine.ps1")
        self.assertEqual(code, 0, out)
        self.assertIn("already installed", out)
        self.assertNotIn("SHA256", out)
        os.remove(os.path.join(engine, "configs", "config.py"))
        code, out = self.ps("install-engine.ps1")
        self.assertEqual(code, 1, out)
        self.assertIn("incomplete", out)
        self.assertIn("configs/config.py", out)

    def test_existing_archive_with_wrong_sha_is_refused_not_deleted(self):
        data = self.make_archive("good")
        self.use_archive(data, sha_override="0" * 64)
        write(self.downloads("RVC20260718Nvidia.7z"), data)
        code, out = self.ps("install-engine.ps1", "-SkipDownload")
        self.assertEqual(code, 1, out)
        self.assertIn("Refusing to install", out)
        self.assertTrue(os.path.exists(self.downloads("RVC20260718Nvidia.7z")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "engine")))

    def test_skip_download_missing_or_partial(self):
        data = self.make_archive("good")
        self.use_archive(data)
        code, out = self.ps("install-engine.ps1", "-SkipDownload")
        self.assertEqual(code, 1, out)
        self.assertIn("-SkipDownload was given", out)
        write(self.downloads("RVC20260718Nvidia.7z"), data[:100])
        code, out = self.ps("install-engine.ps1", "-SkipDownload")
        self.assertEqual(code, 1, out)
        self.assertIn("without -SkipDownload to resume", out)
        self.assertTrue(os.path.exists(self.downloads("RVC20260718Nvidia.7z")))

    def test_nested_package_and_missing_anchor_warning(self):
        self.use_archive(self.make_archive("changed", gui_text="print('changed')\n", top="deep/er/pkg"))
        code, out = self.ps("install-engine.ps1")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "engine", "go-realtime_gui.bat")))
        self.assertIn("no longer contains", out)
        self.assertIn('key="vc"', out)

    def test_failed_extraction_cleans_up(self):
        self.use_archive(os.urandom(4096))  # right size and hash, but not a 7z
        code, out = self.ps("install-engine.ps1")
        self.assertEqual(code, 1, out)
        self.assertIn("7-Zip failed", out)
        self.assertFalse(os.path.exists(self.downloads("_extract")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "engine")))

    def test_tar_fallback_tolerates_skipped_non_ascii_names(self):
        # The real package has 141 CJK-named files (license text, TEMP\ demo audio) that bsdtar
        # skips with exit 1 on a non-UTF-8 code page. Invoke-TarExtract must accept exactly that.
        data = self.make_archive("cjk", extra={"MIT协议": "license", "TEMP/葉月.mp3": "x"})
        archive = os.path.join(self.tmp, "cjk.7z")
        out_dir = os.path.join(self.tmp, "tar-out")
        os.makedirs(out_dir)
        code, out = self.ps_command(
            f". '{os.path.join(self.repo, 'scripts', 'common.ps1')}'; "
            f"$s = @(Invoke-TarExtract '{archive}' '{out_dir}'); 'SKIPPED=' + $s.Count")
        self.assertEqual(code, 0, out)
        skipped = int(re.search(r"SKIPPED=(\d+)", out).group(1))
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "RVC20260718Nvidia", "realtime_gui.py")))
        if skipped == 0:  # a UTF-8 system code page can represent the names
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "RVC20260718Nvidia", "MIT协议")))
        code, out = self.ps_command(f". '{os.path.join(self.repo, 'scripts', 'common.ps1')}'; "
                                    f"Invoke-TarExtract '{os.path.join(self.tmp, 'nope.7z')}' '{out_dir}'")
        self.assertNotEqual(code, 0, out)
        self.assertIn("tar.exe failed", out)


# ---------------------------------------------------------------- launch.ps1


class LaunchTest(ScriptTest):
    def test_friendly_errors(self):
        code, out = self.ps("launch.ps1")
        self.assertEqual(code, 1, out)
        self.assertIn("not installed", out)
        self.assertIn("install-engine.ps1", out)
        write(os.path.join(self.repo, "engine", "runtime", "python.exe"), "")
        code, out = self.ps("launch.ps1", "-Preset", "vctk-p238")
        self.assertEqual(code, 1, out)
        self.assertIn("get-models.ps1 -Voice vctk-p238", out)
        code, out = self.ps("launch.ps1", "-Preset", "nope")
        self.assertEqual(code, 1, out)
        available = re.search(r"Available: (.*)", out).group(1)
        for name in sorted(n[:-5] for n in os.listdir(os.path.join(REPO, "config", "presets"))):
            self.assertIn(name, available)

    def test_presets_listed_even_with_brackets_in_the_repo_path(self):
        repo = self.make_repo("br[1]")
        code, out = self.ps("launch.ps1", "-ListPresets", repo=repo)
        self.assertEqual(code, 0, out)
        for name in ("vctk-p231", "vctk-p238", "vctk-p249"):
            self.assertIn(name, out)

    def test_environment_is_restored_for_the_calling_session(self):
        write(os.path.join(self.repo, "engine", "runtime", "python.exe"), "")  # not runnable: Start-Process fails
        for local in ("models/vctk-p231/Fp231.pth", "models/vctk-p231/added_IVF1216_Flat_nprobe_1_Fp231_v2.index"):
            write(os.path.join(self.repo, *local.split("/")), b"")
        launch = os.path.join(self.repo, "scripts", "launch.ps1")
        code, out = self.ps_command(f"$before = $env:PATH; & '{launch}' -NoCudaGraph; "
                                    "'CUDA=[' + $env:RVC_CUDA_GRAPH + '] SAMEPATH=' + ($env:PATH -eq $before)")
        self.assertIn("ERROR:", out)
        self.assertIn("CUDA=[] SAMEPATH=True", out)


# ---------------------------------------------------------------- measure-delay.ps1 -Analyze


@unittest.skipUnless(FFMPEG, "FFmpeg is needed")
class MeasureDelayAnalyzeTest(ScriptTest):
    EPOCH = 1790300000

    def capture(self, name, mic_expr, cable_expr, cable_offset=0.1, go=None):
        """Two-track .mkv on a shared wall clock; the cable track starts cable_offset s later."""
        path = os.path.join(self.tmp, name + ".mkv")
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", f"aevalsrc='{mic_expr}':s=48000:d=10",
                        "-itsoffset", str(cable_offset), "-f", "lavfi", "-i", f"aevalsrc='{cable_expr}':s=48000:d=10",
                        "-map", "0:a", "-map", "1:a", "-c:a", "pcm_s16le", "-copyts",
                        "-output_ts_offset", str(self.EPOCH), path], check=True)
        if go is not None:
            write(os.path.join(self.tmp, name + ".json"), json.dumps({"go_unix": self.EPOCH + go}))
        return path

    TA_MIC = "if(between(t,4,4.2),0.5*sin(2*PI*440*t),0)"
    TA_CABLE = "if(between(t,4.15,4.35),0.5*sin(2*PI*330*t),0)"  # + 0.1 s offset = 250 ms after the mic

    def analyze(self, path, *args):
        return self.ps("measure-delay.ps1", "-Analyze", path, *args)

    def test_tracks_starting_at_different_times_share_one_clock(self):
        code, out = self.analyze(self.capture("plain", self.TA_MIC, self.TA_CABLE, cable_offset=0.1))
        self.assertEqual(code, 0, out)
        self.assertIn("delay (cable - mic): 250 ms", out)
        code, out = self.analyze(self.capture("late", self.TA_MIC, "if(between(t,1.05,1.25),0.5*sin(2*PI*330*t),0)",
                                              cable_offset=3.2))
        self.assertEqual(code, 0, out)
        self.assertIn("delay (cable - mic): 250 ms", out)

    def test_sound_before_go_is_ignored(self):
        click = "if(between(t,3.0,3.003),0.316,0)+" + self.TA_MIC
        code, out = self.analyze(self.capture("click", click, self.TA_CABLE, go=3.9))
        self.assertEqual(code, 0, out)
        self.assertIn("delay (cable - mic): 250 ms", out)
        self.assertIn("after GO", out)
        code, out = self.analyze(self.capture("click-nogo", click, self.TA_CABLE))
        self.assertIn("1250 ms", out)  # without the GO time the click would count

    def test_silent_cable_track_is_diagnosed(self):
        code, out = self.analyze(self.capture("silent", self.TA_MIC, "0"))
        self.assertEqual(code, 1, out)
        self.assertIn("Cable : silent", out)
        self.assertIn("Output converted voice", out)

    def test_fixed_noise_threshold(self):
        code, out = self.analyze(self.capture("plain", self.TA_MIC, self.TA_CABLE), "-NoiseDb", "-35")
        self.assertEqual(code, 0, out)
        self.assertIn("threshold -35 dB", out)


class StaticChecksTest(unittest.TestCase):
    def test_scripts_parse_and_are_ascii_crlf(self):
        files = [os.path.join(REPO, "scripts", f) for f in os.listdir(os.path.join(REPO, "scripts"))]
        files.append(os.path.join(REPO, "launch.bat"))
        for path in files:
            data = read_bytes(path)
            with self.subTest(path=os.path.basename(path)):
                self.assertTrue(all(b < 128 for b in data), "PS 5.1 reads BOM-less files as ANSI: keep them ASCII")
                self.assertNotIn(b"\n", data.replace(b"\r\n", b""), "expected CRLF line endings")
        ps1 = [p for p in files if p.endswith(".ps1")]
        with tempfile.TemporaryDirectory() as tmp:
            checker = os.path.join(tmp, "parse.ps1")
            write(checker, "$bad = 0\r\nforeach ($f in $args) {\r\n    $e = $null\r\n"
                           "    [void][Management.Automation.Language.Parser]::ParseFile($f, [ref]$null, [ref]$e)\r\n"
                           "    foreach ($x in $e) { $bad++; Write-Output ($f + ': ' + $x.Message) }\r\n}\r\nexit $bad\r\n")
            p = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", checker, *ps1],
                               capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    if sys.platform != "win32":
        sys.exit("These tests need Windows PowerShell.")
    unittest.main(verbosity=2)
