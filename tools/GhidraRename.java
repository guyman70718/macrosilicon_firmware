// Ghidra headless script: rename functions with meaningful names
// Based on MS2107 ROM init sequence analysis
// @category Analysis

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;

public class GhidraRename extends GhidraScript {
    @Override
    public void run() throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        AddressSpace space = currentProgram.getAddressFactory().getDefaultAddressSpace();

        String[][] names = {
            // Chip init sequence
            {"0x5DA4", "chip_init"},
            {"0x700D", "hw_pre_init"},
            {"0x6BD7", "timer0_setup"},
            {"0x6FA7", "gpio_and_port_init"},

            // EEPROM load
            {"0x6656", "eeprom_reload"},
            {"0x50E9", "i2c_bus_init"},
            {"0x688C", "clear_userconfig_ram"},
            {"0x6625", "detect_eeprom_magic"},
            {"0x58C2", "i2c_read_eeprom_header"},
            {"0x4E7E", "eeprom_select_bank"},
            {"0x37CC", "eeprom_load_and_verify"},
            {"0x0E25", "add16_at_ptr"},

            // Config parsing
            {"0x3FC1", "parse_eeprom_config"},
            {"0x58CF", "i2c_read_block"},
            {"0x48EF", "i2c_read_block_alt"},

            // Hook dispatch
            {"0x6F47", "call_normal_hook_if_enabled"},
            {"0x6F9E", "dispatch_to_eeprom_hook"},

            // Video pipeline init
            {"0x3E84", "video_pipeline_init"},
            {"0x6E7D", "video_clock_gate"},
            {"0x60CF", "video_decoder_mode"},
            {"0x6E28", "video_special_mode_init"},
            {"0x67E9", "video_signal_routing"},
            {"0x5DFE", "video_input_select"},
            {"0x6DA0", "video_colorspace_setup"},
            {"0x68E1", "i2c_delay"},
            {"0x6E3A", "video_filter_init"},
            {"0x603D", "video_signal_detect_init"},
            {"0x3D43", "video_calibration"},
            {"0x6A02", "usb_video_endpoint_init"},
            {"0x6A26", "video_scaler_init"},
            {"0x6DB6", "video_deinterlace_init"},
            {"0x69DE", "usb_capture_ctrl_init"},
            {"0x6A4A", "video_timing_init"},
            {"0x6685", "video_standard_apply"},
            {"0x6C10", "usb_frame_mode_select"},
            {"0x6F52", "delay_loop"},
            {"0x7017", "video_post_detect_config"},
            {"0x6EC7", "video_standard_specific"},
            {"0x6F89", "video_threshold_set"},
            {"0x5C8A", "video_sync_init"},
            {"0x670F", "video_scaler_config"},
            {"0x6AF5", "video_set_brightness"},
            {"0x6AD3", "video_set_contrast"},
            {"0x6B17", "video_set_saturation"},
            {"0x6B39", "video_set_hue"},
            {"0x6087", "video_pipeline_reset"},

            // Audio
            {"0x6E8D", "set_audio_output_mode"},

            // USB descriptors
            {"0x1E57", "build_usb_descriptors"},
            {"0x0D30", "configure_usb_endpoint"},
            {"0x10DB", "multiply_byte"},

            // Main loop
            {"0x40E4", "main_loop_dispatch"},
            {"0x2A9B", "signal_change_handler"},
            {"0x5A18", "update_video_params"},
            {"0x4DD8", "monitor_signal_presence"},
            {"0x6BBA", "monitor_signal_standard"},
            {"0x65F3", "handle_signal_anomaly"},

            // Utilities
            {"0x6FF8", "set_register_bits"},
            {"0x6FF1", "write_register_value"},
            {"0x6A8F", "write_register_masked"},
            {"0x68DA", "short_delay"},
            {"0x6F2F", "clear_video_regs"},

            // Known from earlier analysis
            {"0x0000", "reset_vector"},
            {"0x1F17", "copy_vid_pid_from_eeprom"},
            {"0x5323", "i2c_write_byte"},
            {"0x54AE", "usb_irq_handler"},
            {"0x5934", "i2c_read_byte"},
            {"0x68BD", "i2c_start"},
            {"0x6B5B", "i2c_stop"},
            {"0x5C29", "video_capture_setup"},
        };

        int renamed = 0;
        for (String[] entry : names) {
            long addr = Long.parseLong(entry[0].substring(2), 16);
            String name = entry[1];
            Address a = space.getAddress(addr);
            Function func = fm.getFunctionAt(a);
            if (func != null) {
                func.setName(name, SourceType.USER_DEFINED);
                renamed++;
            }
        }
        println("Renamed " + renamed + " functions");
    }
}
