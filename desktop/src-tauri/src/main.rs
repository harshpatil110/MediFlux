// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem};

#[tauri::command]
fn get_desktop_runtime_info() -> serde_json::Value {
    serde_json::json!({
        "platform": "windows",
        "runtime": "tauri",
        "version": "1.0.0",
        "is_desktop": true
    })
}

fn main() {
    let open_item = CustomMenuItem::new("open".to_string(), "Open MediFlux Control Tower");
    let quit_item = CustomMenuItem::new("quit".to_string(), "Quit MediFlux");
    let tray_menu = SystemTrayMenu::new()
        .add_item(open_item)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(quit_item);
    let system_tray = SystemTray::new().with_menu(tray_menu);

    tauri::Builder::default()
        .system_tray(system_tray)
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
                "open" => {
                    if let Some(window) = app.get_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "quit" => {
                    std::process::exit(0);
                }
                _ => {}
            },
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![get_desktop_runtime_info])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
