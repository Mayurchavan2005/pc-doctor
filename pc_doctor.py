"""
PC Doctor
Made by Mayur (@vibe.coderr_)

Problem: A PC becomes slow, but Windows only shows numbers
like CPU 90% and RAM 85%. Most people do not know what
those numbers mean, or what is safe to delete.
This tool checks the PC and explains the problem in
plain English, and only offers to clean safe temp files.

Run:
    python pc_doctor.py
    python pc_doctor.py --clean
    python pc_doctor.py --clean --dry-run
"""

import argparse
import os
import shutil
import tempfile
import time
from pathlib import Path

import psutil


def format_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_folder_size(folder):
    total = 0
    for root, _, files in os.walk(folder):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except (OSError, FileNotFoundError):
                continue
    return total


def get_temp_folder():
    if os.name == "nt":
        return Path(os.environ.get("TEMP", tempfile.gettempdir()))
    return Path(tempfile.gettempdir())


def collect_system_stats():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    battery = psutil.sensors_battery()
    boot_time = psutil.boot_time()
    uptime_hours = (time.time() - boot_time) / 3600

    temp_folder = get_temp_folder()
    temp_size = get_folder_size(temp_folder) if temp_folder.exists() else 0

    return {
        "cpu": cpu,
        "ram_percent": memory.percent,
        "ram_used": memory.used,
        "ram_total": memory.total,
        "disk_percent": disk.percent,
        "disk_used": disk.used,
        "disk_total": disk.total,
        "battery_percent": battery.percent if battery else None,
        "battery_plugged": battery.power_plugged if battery else None,
        "uptime_hours": uptime_hours,
        "temp_size": temp_size,
        "temp_folder": str(temp_folder),
    }


def get_top_processes(limit=5):
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            if info["memory_percent"] and info["memory_percent"] > 0.5:
                processes.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda p: p["memory_percent"], reverse=True)
    return processes[:limit]


def calculate_health_score(stats):
    score = 100

    if stats["ram_percent"] > 85:
        score -= 25
    elif stats["ram_percent"] > 70:
        score -= 15

    if stats["cpu"] > 80:
        score -= 20
    elif stats["cpu"] > 60:
        score -= 10

    if stats["disk_percent"] > 90:
        score -= 25
    elif stats["disk_percent"] > 80:
        score -= 15

    if stats["temp_size"] > 1024 * 1024 * 1024:
        score -= 10
    elif stats["temp_size"] > 500 * 1024 * 1024:
        score -= 5

    if stats["uptime_hours"] > 72:
        score -= 5

    return max(score, 0)


def explain_in_plain_english(stats, score, top_processes):
    lines = []

    if score >= 80:
        lines.append("PC health is good. No major problem found.")
    elif score >= 60:
        lines.append("PC is okay, but it may feel slow. Check the points below.")
    else:
        lines.append("PC needs attention. Fix the problems below first.")

    if stats["ram_percent"] > 85:
        lines.append(f"RAM is {stats['ram_percent']:.0f}% full. Close extra Chrome tabs, and do not run heavy apps at the same time.")
    elif stats["ram_percent"] > 70:
        lines.append(f"RAM is {stats['ram_percent']:.0f}% used. It will work for now, but it will slow down if you open more apps.")

    if stats["cpu"] > 80:
        lines.append(f"CPU is at {stats['cpu']:.0f}%. One app is taking too much load, see the top processes below.")
    elif stats["cpu"] > 60:
        lines.append("CPU load is a bit high. This is normal if video editing or a game is running.")

    if stats["disk_percent"] > 90:
        lines.append(f"Disk is {stats['disk_percent']:.0f}% full. Delete old videos or large files, otherwise Windows will slow down.")
    elif stats["disk_percent"] > 80:
        lines.append(f"Disk is {stats['disk_percent']:.0f}% full. Free up some space.")

    if stats["temp_size"] > 500 * 1024 * 1024:
        lines.append(f"Temp files are {format_size(stats['temp_size'])}. These are safe to delete, use --clean to remove them.")
    else:
        lines.append(f"Temp files are only {format_size(stats['temp_size'])}. Cleaning them will not make a difference.")

    if stats["uptime_hours"] > 72:
        lines.append(f"PC has been running for {stats['uptime_hours']:.0f} hours without a restart. Restart once, it will clear the RAM.")

    if top_processes:
        heavy = top_processes[0]
        if heavy["memory_percent"] > 15:
            lines.append(f"{heavy['name']} is using the most RAM ({heavy['memory_percent']:.1f}%). Close it if you are not using it.")

    return lines


def clean_temp_files(dry_run=False):
    temp_folder = get_temp_folder()
    removed_count = 0
    freed = 0

    print(f"\nTemp folder: {temp_folder}")
    if dry_run:
        print("Dry run - nothing will be deleted, this only shows what would happen.")

    for item in temp_folder.iterdir():
        try:
            if item.is_file():
                size = item.stat().st_size
                if not dry_run:
                    item.unlink()
                removed_count += 1
                freed += size
            elif item.is_dir():
                size = get_folder_size(item)
                if not dry_run:
                    shutil.rmtree(item, ignore_errors=True)
                removed_count += 1
                freed += size
        except (OSError, PermissionError):
            continue

    print(f"Files removed: {removed_count}, space freed: {format_size(freed)}")
    return removed_count, freed


def build_report(stats, score, advice, top_processes):
    report = []
    report.append("PC Doctor - Report")
    report.append(f"Health Score: {score}/100")
    report.append("")
    report.append(f"CPU: {stats['cpu']:.1f}%")
    report.append(f"RAM: {stats['ram_percent']:.1f}% ({format_size(stats['ram_used'])} / {format_size(stats['ram_total'])})")
    report.append(f"Disk: {stats['disk_percent']:.1f}% ({format_size(stats['disk_used'])} / {format_size(stats['disk_total'])})")
    if stats["battery_percent"] is not None:
        report.append(f"Battery: {stats['battery_percent']:.0f}%")
    report.append(f"Uptime: {stats['uptime_hours']:.1f} hours")
    report.append(f"Temp files: {format_size(stats['temp_size'])}")
    report.append("")
    report.append("Explanation in plain English:")
    for line in advice:
        report.append(f"- {line}")
    report.append("")
    report.append("Top processes (by RAM use):")
    for proc in top_processes:
        report.append(f"- {proc['name']} - {proc['memory_percent']:.1f}% RAM, {proc['cpu_percent']:.1f}% CPU")
    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="PC Doctor - find out why your PC is slow, in plain English")
    parser.add_argument("--clean", action="store_true", help="Clean safe temp files")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would happen, delete nothing")
    parser.add_argument("--report", action="store_true", help="Save the report to pc_report.txt")
    args = parser.parse_args()

    stats = collect_system_stats()
    top_processes = get_top_processes()
    score = calculate_health_score(stats)
    advice = explain_in_plain_english(stats, score, top_processes)

    print("\nPC Doctor")
    print("=" * 40)
    print(f"Health Score: {score}/100")
    print(f"CPU: {stats['cpu']:.1f}% | RAM: {stats['ram_percent']:.1f}% | Disk: {stats['disk_percent']:.1f}%")
    if stats["battery_percent"] is not None:
        print(f"Battery: {stats['battery_percent']:.0f}%")
    print(f"Uptime: {stats['uptime_hours']:.1f} hours | Temp: {format_size(stats['temp_size'])}")
    print("=" * 40)

    print("\nExplanation in plain English:")
    for line in advice:
        print(f"- {line}")

    print("\nTop processes:")
    for proc in top_processes:
        print(f"- {proc['name']} - {proc['memory_percent']:.1f}% RAM")

    if args.clean:
        try:
            answer = input("\nClean temp files? These are safe files. (y/n): ").strip().lower()
        except EOFError:
            answer = "n"
        if answer == "y":
            clean_temp_files(dry_run=args.dry_run)
        else:
            print("Okay, nothing was deleted.")

    if args.report:
        report_text = build_report(stats, score, advice, top_processes)
        Path("pc_report.txt").write_text(report_text, encoding="utf-8")
        print("\nReport saved: pc_report.txt")


if __name__ == "__main__":
    main()
