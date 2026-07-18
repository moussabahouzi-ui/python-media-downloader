# -*- coding: utf-8 -*-
import os
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

class VideoDownloader:
    def __init__(self, output_dir="downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            filename = d.get('filename', 'Unknown File')
            percent = d.get('_percent_str', '0.0%')
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            print(f"[DOWNLOADING] Target: {filename} | Progress: {percent} | Speed: {speed} | ETA: {eta}")
        elif d['status'] == 'finished':
            print(f"[COMPLETED] Extraction finished successfully: {d['filename']}")

    def get_video_info(self, url: str) -> dict:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return {
                    "success": True,
                    "title": info.get("title", "Unknown Title"),
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", "Unknown Author"),
                    "thumbnail": info.get("thumbnail", ""),
                    "platform": info.get("extractor_key", "GenericExtractor")
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

    def download_single(self, url: str) -> dict:
        output_template = str(self.output_dir / '%(title)s.%(ext)s')
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': output_template,
            'progress_hooks': [self._progress_hook],
            'ignoreerrors': False,
            'merge_output_format': 'mp4',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filename)
                final_path = f"{base}.mp4" if os.path.exists(f"{base}.mp4") else filename
                return {"success": True, "title": info.get("title", "Unknown"), "file_path": final_path}
            except Exception as e:
                return {"success": False, "url": url, "error": str(e)}

    def download_bulk(self, urls: list, max_workers: int = 3) -> list:
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(self.download_single, url): url for url in urls}
            for future in future_to_url:
                url = future_to_url[future]
                try:
                    data = future.result()
                    results.append(data)
                except Exception as exc:
                    results.append({"success": False, "url": url, "error": str(exc)})
        return results
