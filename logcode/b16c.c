#include <stdio.h>
#include <stdint.h>
#include "change_byte_sequence.h"
#include "host.h"

void get_tbs_index_String_no_asn(int num, char *output) {
    switch (num) {
        case 0:
            strcpy(output, "TBS_Index_0");
            break;
        case 1:
            strcpy(output, "TBS_Index_1");
            break;
        case 2:
            strcpy(output, "TBS_Index_2");
            break;
        case 3:
            strcpy(output, "TBS_Index_3");
            break;
        case 4:
            strcpy(output, "TBS_Index_4");
            break;
        case 5:
            strcpy(output, "TBS_Index_5");
            break;
        case 6:
            strcpy(output, "TBS_Index_6");
            break;
        case 7:
            strcpy(output, "TBS_Index_7");
            break;
        case 8:
            strcpy(output, "TBS_Index_8");
            break;
        case 9:
            strcpy(output, "TBS_Index_9");
            break;
        case 10:
            strcpy(output, "TBS_Index_10");
            break;
        case 11:
            strcpy(output, "TBS_Index_11");
            break;
        case 12:
            strcpy(output, "TBS_Index_12");
            break;
        case 13:
            strcpy(output, "TBS_Index_13");
            break;
        case 14:
            strcpy(output, "TBS_Index_14");
            break;
        case 15:
            strcpy(output, "TBS_Index_15");
            break;
        case 16:
            strcpy(output, "TBS_Index_16");
            break;
        case 17:
            strcpy(output, "TBS_Index_17");
            break;
        case 18:
            strcpy(output, "TBS_Index_18");
            break;
        case 19:
            strcpy(output, "TBS_Index_19");
            break;
        case 20:
            strcpy(output, "TBS_Index_20");
            break;
        case 21:
            strcpy(output, "TBS_Index_21");
            break;
        case 22:
            strcpy(output, "TBS_Index_22");
            break;
        case 23:
            strcpy(output, "TBS_Index_23");
            break;
        case 24:
            strcpy(output, "TBS_Index_24");
            break;
        case 25:
            strcpy(output, "TBS_Index_25");
            break;
        case 26:
            strcpy(output, "TBS_Index_26");
            break;
        case 27:
            strcpy(output, "TBS_Index_26A");
            break;
        case 28:
            strcpy(output, "TBS_Index_27");
            break;
        case 29:
            strcpy(output, "TBS_Index_28");
            break;
        case 30:
            strcpy(output, "TBS_Index_29");
            break;
        case 31:
            strcpy(output, "TBS_Index_30");
            break;
        case 32:
            strcpy(output, "TBS_Index_31");
            break;
        case 33:
            strcpy(output, "TBS_Index_32");
            break;
        case 34:
            strcpy(output, "TBS_Index_32A");
            break;
        case 35:
            strcpy(output, "TBS_Index_33");
            break;
        case 36:
            strcpy(output, "Unknown36");
            break;
        case 37:
            strcpy(output, "Unknown37");
            break;
        case 38:
            strcpy(output, "Unknown38");
            break;
        case 39:
            strcpy(output, "Unknown39");
            break;
        default:
            strcpy(output, "invalid");
            break;
    }
}


void decode_B16C_v48_no_asn(uint8_t *hex_data, size_t length, int *index, uint64_t time_in_us_total, uint16_t logcode)
{
    /*S_H*/
    int start_S_H = *index;
    *index+=4;
    int version = hex_data[start_S_H];
    int num_record = (hex_data[start_S_H+1]&0xFC)>>2;

    print_hex(hex_data,start_S_H-12,*index);
    fflush(stdout);

    int first_sub_frame_number = 0;
    int first_sys_frame_number = 0;

    for(int i=0;i<num_record;i++)
    {
        int start_record = *index;
        convert_endianess(hex_data, index, 2);
        int subfn = (hex_data[start_record]&0x3C)>>2;
        int sysfn = ((hex_data[start_record]&0x03)<<8)|(hex_data[start_record+1]);            
        int num_ul_grant = (hex_data[start_record]&0xC0)>>6;

        if(i==0)
        {
            first_sub_frame_number = subfn;
            first_sys_frame_number = sysfn;
        }

        int is_num_ul_grant=0;

        // UL grant
        if(num_ul_grant!=0)
        {
            int start_UL = *index;
            *index+=126;
            int mcs_index = (hex_data[start_UL+5]&0xF8)>>3;
            int redundancy_version = (hex_data[start_UL+5]&0x06)>>1;
            int tbs_index = (hex_data[start_UL+6]&0x3F);
            int num_of_resource_blocks = (hex_data[start_UL+8]&0x7F);


            char tbs_index_1[50];
            get_tbs_index_String_no_asn(tbs_index, tbs_index_1);
            // printf("%02X\t%llu\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n",
            //         logcode, time_in_us_total, version, num_record, 
            //         first_sub_frame_number, first_sys_frame_number,
            //         subfn, sysfn, mcs_index, redundancy_version, num_of_resource_blocks);

            is_num_ul_grant = 1;

            printf("AAAAAAA\n");
            fflush(stdout);

            FILE *fp_B16C = fopen("B16C_report.txt", "a+");
            if (fp_B16C == NULL) 
            {
                fprintf(stderr, "Error: Cannot open B064_report.txt\n");
                return;  // 
            }
            // fprintf(fp_B16C, "%02X\t%llu\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t%d\t%d\t%d\t%d\n",
            //                     logcode, time_in_us_total, version, num_record, 
            //                     first_sub_frame_number, first_sys_frame_number,
            //                     subfn, sysfn, mcs_index, redundancy_version, tbs_index_1, num_of_resource_blocks,
            //                     crc_check, check_format, pkt_type);
            fprintf(fp_B16C, "%02X\t%llu\t%d\t%d\t%d\t%d\t%d\t%s\t%d\t%d\t\n",
                    logcode, time_in_us_total, version,  
                    subfn, sysfn, mcs_index, redundancy_version, tbs_index_1, num_of_resource_blocks,
                    is_num_ul_grant);
            fclose(fp_B16C);

            printf("BBBBBBB\n");
            fflush(stdout);
        }
        else // dl grant
        {
            // is_num_ul_grant=0;

            // int start_UL = *index;
            // *index+=126;
            // int mcs_index = (hex_data[start_UL+5]&0xF8)>>3;
            // int redundancy_version = (hex_data[start_UL+5]&0x06)>>1;
            // int tbs_index = (hex_data[start_UL+6]&0x3F);
            // int num_of_resource_blocks = (hex_data[start_UL+8]&0x7F);

            // char tbs_index_1[50];
            // get_tbs_index_String_no_asn(tbs_index, tbs_index_1);
            // printf("%02X\t%llu\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n",
            //         logcode, time_in_us_total, version, num_record, 
            //         first_sub_frame_number, first_sys_frame_number,
            //         subfn, sysfn, mcs_index, redundancy_version, num_of_resource_blocks);

            // FILE *fp_B16C = fopen("B16C_report.txt", "a+");
            // // fprintf(fp_B16C, "%02X\t%llu\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t%d\t%d\t%d\t%d\n",
            // //                     logcode, time_in_us_total, version, num_record, 
            // //                     first_sub_frame_number, first_sys_frame_number,
            // //                     subfn, sysfn, mcs_index, redundancy_version, tbs_index_1, num_of_resource_blocks,
            // //                     crc_check, check_format, pkt_type);
            // fprintf(fp_B16C, "%02X\t%llu\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t%d\t%d\n",
            //         logcode, time_in_us_total, version, num_record, 
            //         first_sub_frame_number, first_sys_frame_number,
            //         subfn, sysfn, mcs_index, redundancy_version, tbs_index_1, num_of_resource_blocks,
            //         is_num_ul_grant);

            // fclose(fp_B16C);

            // FILE *fp_B16C_UL_0 = fopen("B16C_UL_judge_0.txt", "a+");
            // for(int k=0;k<128;k++)
            // {
            //     fprintf(fp_B16C_UL_0, "%02X ", hex_data[start_record+k]);
            // }
            // fprintf(fp_B16C_UL_0,"\n");
            // fclose(fp_B16C_UL_0);

        }
    }
}