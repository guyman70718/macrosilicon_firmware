// Ghidra headless script: rename MS2109 ROM functions with meaningful names
// Based on boot sequence analysis and stock EEPROM disassembly
// @category Analysis

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;

public class GhidraRename2109 extends GhidraScript {
    @Override
    public void run() throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        AddressSpace space = currentProgram.getAddressFactory().getDefaultAddressSpace();

        String[][] names = {
            // Reset and interrupt vectors
            {"0x0000", "reset_vector"},
            {"0x0003", "ext0_isr"},
            {"0x000B", "timer0_isr"},
            {"0x0013", "ext1_isr"},
            {"0x001B", "timer1_isr"},
            {"0x0023", "serial_isr"},

            // Boot and init (from boot_annotated.md)
            {"0x4149", "chip_init"},
            {"0x48E6", "hw_init_core"},

            // I2C primitives (from ms-tools)
            {"0x4648", "i2c_write_byte"},
            {"0x4CF3", "i2c_read_byte"},
            {"0x6A8C", "i2c_start"},
            {"0x6ABA", "i2c_stop"},

            // EEPROM
            {"0x5F19", "eeprom_reload"},

            // Video processing
            {"0x6069", "video_process_core"},
            {"0x6345", "hw_init_with_table"},

            // Stock EEPROM overlay functions (0xD000+ region)
            // These are byte-identical in ROM and stock EEPROM
            {"0xD03A", "stock_cmd_dispatch_table"},
            {"0xD104", "stock_cmd_handler"},
            {"0xD212", "mul16"},
            {"0xD223", "jump_table_engine"},
            {"0xD27D", "math_func"},
            {"0xD2BD", "hw_init_thunk"},
            {"0xD2C1", "video_process_thunk"},
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
            } else {
                println("No function at 0x" + entry[0] + " (" + name + ")");
            }
        }
        println("Renamed " + renamed + " functions");
    }
}
