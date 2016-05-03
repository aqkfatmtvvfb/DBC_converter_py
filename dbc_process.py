# coding=utf-8
import re
import sys

class Message(object):
    def __init__(self, line):
        line = line.strip()
        m = re.match(r'^BO_\s+(\d+)\s+(\w+):\s+(\d+)\s+(\w+)', line)
        assert m is not None, 'Message 正则化失败'
        self.id_in_dbc = int(m.group(1))
        if 1 == (self.id_in_dbc >> 31):
            self.isExtend = True
        else:
            self.isExtend = False
        self.message_id = self.id_in_dbc & 0x7FFFFFFF
        self.message_name = m.group(2)
        self.message_size = int(m.group(3))
        self.transmitter = m.group(4)
        self.SignalList = []
        self.attri_list = []

    def add_signal(self, line):
        self.SignalList.append(Signal(line))


class Signal(object):
    def __init__(self, line):
        line = line.strip()
        # SG_ d : 8|8@1- (1,0) [0|0] ""  Txx
        # SG_ n2 m1 : 2|1@1- (1,0) [0|0] ""  Txx
        # SG_ n1 m0 : 2|1@1- (1,0) [0|0] ""  Txx
        # SG_ C M : 0|2@1- (1,0) [0|0] ""  Txx
        pattern = r'^SG_\s+(\w+)\s+([ Mm0-9]{0,})\s*[:]\s+(\d+)[|](\d+)[@]([01])([-+])\s+[(]([-.0-9]+)' \
                  r'[,]([-.0-9]+)[)]\s+[[]([-.0-9]+)[|]([-.0-9]+)[]]\s+["]([\S]*)["]\s+(\w+)'
        m = re.match(pattern, line)
        assert m is not None, 'Signal 正则化失败'
        self.signal_name = m.group(1)
        self.mutiplexer_indicator = m.group(2)
        start_bit_in_dbc = int(m.group(3))
        self.signal_size = int(m.group(4))
        self.byte_order = m.group(5)
        self.value_type = m.group(6)
        self.factor = float(m.group(7))
        self.offset = float(m.group(8))
        self.minimum = float(m.group(9))
        self.maximum = float(m.group(10))
        self.unit = m.group(11)
        self.receiver_list = m.group(12).split(' ')
        self.comment = ''
        self.valueDescriptionList = []

        pattern=r'([ Mm]){0,1}([0-9]{0,})'
        m = re.match(pattern, self.mutiplexer_indicator)
        assert m is not None, 'mutiplexer_indicator 正则化失败'
        self.mutiplexer_flag=m.group(1)
        self.mutiplexer_switch_value = m.group(2)
        if self.byte_order == '0':
            self.byte_order = 'Motorola'
        else:  # 1
            self.byte_order = 'Intel'
        if self.value_type == '+':
            self.value_type = 'unsigned'
        else:  # -
            self.value_type = 'signed'

        if self.byte_order == 'Intel':
            self.start_bit = start_bit_in_dbc
        else:
            self.start_bit = calculate_LSB_motorola(start_bit_in_dbc,  self.signal_size)


class Comment(object):
    def __init__(self, raw):
        raw = raw.strip()
        m = re.match(r'^CM_ SG_\s+(\d+)\s+(\w+)\s+"([\s\S]*)";$', raw)
        assert m is not None, 'Comment 正则化失败'
        self.message_id = int(m.group(1))
        self.signal_name = m.group(2)
        self.cm_string = m.group(3)


class Val(object):
    def __init__(self, raw):
        raw = raw.strip()
        # VAL_ 1130 DircnIndLampSwStsHSC2 0 "off" 1 "Left on" 2 "Right on" 3 "reserve" ;
        m = re.match(r'^VAL_\s+(\d+)\s+(\w+)\s+([\s\S]*)\s;$', raw)
        assert m is not None, 'Val 正则化失败'
        self.message_id = int(m.group(1))
        self.signal_name = m.group(2)
        self.raw_value_description = m.group(3)
        rawValueDescriptionList = self.raw_value_description.strip().split('"')
        nLength = len(rawValueDescriptionList)-1
        assert (nLength % 2) == 0, 'ValueDescription 不为偶数'
        self.valueDescriptionList = []
        for i in range(int(nLength / 2)):
            self.valueDescriptionList.append([rawValueDescriptionList[i * 2], rawValueDescriptionList[i * 2 + 1]])


class AttributeDef(object):
    def __init__(self, raw):
        raw = raw.strip()
        m = re.match(r'^BA_DEF_\s?( |BU_ |BO_ |SG_ |EV_ |)\s?"(\w+)"\s+(\w+)([\s\S]*);$', raw)
        self.type = m.group(1)
        self.name = m.group(2)
        self.value_type = m.group(3)
        self.rest = m.group(4)
        if self.value_type == 'STRING':
            self.default_value = '""'
        elif self.value_type == 'ENUM':
            self.default_value = r'"0"'
        else:
            self.default_value = str(0)


class Attrbute(object):
    def __init__(self, raw):
        raw = raw.strip()
        m = re.match(r'^BA_\s"(\w+)"\s([\s\S]*)(?=;);$', raw)
        self.name = m.group(1)
        self.rest = m.group(2)
        self.node_name = ''
        self.message_id = ''
        self.attribute_value = ''
        self.signal_name = ''
        self.env_var_name = ''
        temp_list = self.rest.strip('"').split()
        if temp_list[0] == 'BU_':
            self.node_name = temp_list[1]
        elif temp_list[0] == 'BO_':
            self.message_id = temp_list[1]
            self.attribute_value = temp_list[2]
        elif temp_list[0] == 'SG_':
            self.message_id = temp_list[1]
            self.signal_name = temp_list[2]
            self.attribute_value = temp_list[3]
        elif temp_list[0] == 'EV_':
            self.env_var_name = temp_list[1]
            self.attribute_value = temp_list[2]
        else:
            self.attribute_value = temp_list[0]


def calculate_LSB_motorola(MSB, length):
    order_list = []
    for j in range(0, 8, 1):
        for i in range(7, -1, -1):
            order_list.append(j*8+i)
    for i in range(len(order_list)):
        if MSB == order_list[i]:
            position = i
    LSB = order_list[position+length-1]
    return LSB


def CM_preprocess(dbc_fp):
    dbc_lines = dbc_fp.readlines()
    CM_list_raw = []
    is_Mutilines = False
    for line in dbc_lines:
        if is_Mutilines is False:
            line = line.lstrip()
            if line[0:8] == 'CM_ SG_ ':
                string = line
                if line[-2] == ';' and line[-1] == '\n':
                    is_Mutilines = False
                    CM_list_raw.append(string)
                else:
                    is_Mutilines = True
        else:
            string = string + line
            if len(line) >= 2:
                if line[-2] == ';' and line[-1] == '\n':
                    is_Mutilines = False
                    CM_list_raw.append(string)
    return CM_list_raw


def CM_process(CM_list_raw):
    CM_list=[]
    for cm_raw in CM_list_raw:
        CM_list.append(Comment(cm_raw))
    return CM_list


def ansignment_val(message_list, value_descrip_list):
    for message in message_list:
        for signal in message.SignalList:
            for value_descrip in value_descrip_list:
                if value_descrip.message_id == message.id_in_dbc and value_descrip.signal_name == signal.signal_name:
                    signal.valueDescriptionList = value_descrip.valueDescriptionList
    return message_list


def ansignment_cm(message_list, CM_list):
    for message in message_list:
        for signal in message.SignalList:
            for cm in CM_list:
                if cm.message_id == message.id_in_dbc and cm.signal_name == signal.signal_name:
                    signal.comment = cm.cm_string
    return message_list


def ansignment_attrib_def(attrib_def_list, line):
    raw = line.strip()
    m = re.match(r'^BA_DEF_DEF_\s+"(\w+)"\s+("?\w*"?)([\s\S]*);$', raw)
    name = m.group(1)
    value = m.group(2)
    rest = m.group(3)
    for attrib_def in attrib_def_list:
        if name == attrib_def.name:
            attrib_def.default_value = value
    return


def ansignment_attri(message_list, attrib_def_list, attrib_list):
    for message in message_list:
        message.attri_list=[]
        for attrib_def in attrib_def_list:
            if attrib_def.type.strip() == 'BO_':
                message.attri_list.append([attrib_def.name,attrib_def.default_value])
        for signal in message.SignalList:
            signal.attri_list=[]
            for attrib_def in attrib_def_list:
                if attrib_def.type.strip() == 'SG_':
                    signal.attri_list.append([attrib_def.name,attrib_def.default_value])
    for message in message_list:
        for message_attri_name,message_attri_value in message.attri_list:
            for attrib in attrib_list:
                if attrib.message_id == str(message.id_in_dbc) and attrib.name.strip() == message_attri_name.strip():
                    message_attri_value = attrib.attribute_value
                    for i in range(len(message.attri_list)):
                        if message.attri_list[i][0].strip() == attrib.name.strip():
                            message.attri_list[i][1]=message_attri_value
        for ssignal in message.SignalList:
            for signal_attri_name,signal_attri_value in ssignal.attri_list:
                for attrib in attrib_list:
                    if attrib.message_id == str(message.id_in_dbc) and attrib.name.strip() == signal_attri_name.strip() and attrib.signal_name.strip() == ssignal.signal_name.strip():
                        signal_attri_value = attrib.attribute_value
                        for i in range(len(ssignal.attri_list)):
                            if ssignal.attri_list[i][0].strip() == attrib.name.strip():
                                ssignal.attri_list[i][1] = signal_attri_value
    return


def process_dbc(dbc_fp):
    # 将CM的多行内容存入List
    CM_list_raw = CM_preprocess(dbc_fp)
    CM_list = CM_process(CM_list_raw)
    # 处理其他的元素
    message_list = []
    value_descrip_list = []
    attrib_def_list = []
    attrib_list = []
    dbc_fp.seek(0)
    dbc_lines = dbc_fp.readlines()
    for line in dbc_lines:
        line = line.strip()
        if line[0:4] == 'BU_:':
            pass
        elif line[0:4] == 'BO_ ':
            message_list.append(Message(line))
        elif line[0:4] == 'SG_ ':
            message_list[-1].add_signal(line)
        elif line[0:5] == 'VAL_ ':
            value_descrip_list.append(Val(line))
        elif line[0:8] == 'BA_DEF_ ':
            attrib_def_list.append(AttributeDef(line))
        elif line[0:12] == 'BA_DEF_DEF_ ':
            ansignment_attrib_def(attrib_def_list, line)
        elif line[0:4] == 'BA_ ':
            attrib_list.append(Attrbute(line))
    ansignment_val(message_list, value_descrip_list)
    ansignment_cm(message_list, CM_list)
    ansignment_attri(message_list, attrib_def_list, attrib_list)
    return message_list, attrib_def_list


def write_csv(csv_name, message_list, attrib_def_list, write_val=False, write_comment=False, write_attri=False):
    with open(csv_name+'_g.csv', 'w') as csv_fp:
        csv_fp.write(r'message_id,isExtend,message_name,message_size,transmitter,')
        if write_attri is True:
            for message_attri_name, message_attri_value in message_list[0].attri_list:
                csv_fp.write(r'%s' % message_attri_name)
                for attrib_def in attrib_def_list:
                    if attrib_def.name == message_attri_name:
                        csv_fp.write(r'(%s),' % attrib_def.value_type)
        csv_fp.write(r'receiver,signal_name,mutiplexer_flag,mutiplexer_switch_value,start_bit,'
                     r'signal_size,byte_order,value_type,factor,offset,minimum,maximum,unit,')
        if write_attri is True:
            for signal_attri_name, signal_attri_value in message_list[0].SignalList[0].attri_list:
                csv_fp.write(r'%s' % signal_attri_name)
                for attrib_def in attrib_def_list:
                    if attrib_def.name == signal_attri_name:
                        csv_fp.write(r'(%s),' % attrib_def.value_type)
        if write_val is True:
            csv_fp.write(r'value_description,')
        if write_comment is True:
            csv_fp.write(r'comment,')

        position = csv_fp.tell()
        csv_fp.seek(position - 1, 0)
        csv_fp.write('\n')

        for message in message_list:
            for signal in message.SignalList:
                csv_fp.write(r'%d,%s,%s,%d,%s,' % (message.message_id,
                                                   message.isExtend,
                                                   message.message_name,
                                                   message.message_size,
                                                   message.transmitter))
                if write_attri is True:
                    for message_attri_name, message_attri_value in message.attri_list:
                        csv_fp.write(r'%s,' % message_attri_value)
                for receiver in signal.receiver_list:
                    csv_fp.write(r'%s ' % receiver)
                position=csv_fp.tell()
                csv_fp.seek(position-1, 0)
                csv_fp.write(r',')
                data_output = (signal.signal_name,
                               signal.mutiplexer_flag,
                               signal.mutiplexer_switch_value,
                               signal.start_bit,
                               signal.signal_size,
                               signal.byte_order,
                               signal.value_type,
                               signal.factor,
                               signal.offset,
                               signal.minimum,
                               signal.maximum,
                               signal.unit)
                csv_fp.write(r'%s,%s,%s,%d,%d,%s,%s,%f,%f,%f,%f,%s,' % data_output)
                if write_attri is True:
                    for signal_attri_name, signal_attri_value in signal.attri_list:
                        csv_fp.write(r'%s,' % signal_attri_value)

                if write_val is True:
                    csv_fp.write(r'"')
                    for value, descri in signal.valueDescriptionList:
                        csv_fp.write(r'%s {%s}' % (value, descri))
                        csv_fp.write('\n')
                    csv_fp.write(r'"')
                    csv_fp.write(r',')
                if write_comment is True:
                    csv_fp.write(r'"%s",' % signal.comment)

                position = csv_fp.tell()
                csv_fp.seek(position - 1, 0)
                csv_fp.write('\n')
    return


def dbc2csv(dbc_name,write_val=False, write_comment=False, write_attri=False):
    """
        简介：
            用于将dbc转为csv，filename.csv生成filename_g.dbc
        输入定义：
            必选参数：
                dbc_name：dbc文件名，不包含后缀名，即.之前的部分
            可选参数：
                write_val：是否输出value description，默认为False
                write_comment：是否输出comment，默认为False
                write_attri：是否输出自定义的attribution，默认为False
        其他说明：
            1. 输出的顺序为：message的属性、message的attribution、signal的属性、signal的attribution、value description、comment
            2. 输出第一行为表头，attribution的表头定义为 name(value_type)
        调用示例：
            dbc_process test： 处理test.dbc,不输出value description、comment、attribution
            dbc_process test True： 处理test.dbc。输出value description，不输出comment、attribution
        作者信息：
            Wang Yu, wangyu_1988@126.com
        版本号：
            1.0 20160401
        """
    with open(dbc_name + '.dbc', 'r') as dbc_fp:
        message_list, attrib_def_list = process_dbc(dbc_fp)
        write_csv(dbc_name, message_list, attrib_def_list, write_val, write_comment, write_attri)
    return


if __name__ == "__main__":
    dbc_name = 'test2'
    dbc2csv(dbc_name, True, True, True)


    # if len(sys.argv) == 5:
    #     if sys.argv[2] == 'True':
    #         write_val = True
    #     else:
    #         write_val = False
    #     if sys.argv[3] == 'True':
    #         write_comment = True
    #     else:
    #         write_comment = False
    #     if sys.argv[4] == 'True':
    #         write_attri = True
    #     else:
    #         write_attri = False
    #
    #     dbc2csv(sys.argv[1], write_val, write_comment, write_attri)
    # else:
    #     print('输入错误！')



