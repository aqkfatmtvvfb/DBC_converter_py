# coding=utf-8
import re
import sys


class Config(object):
    def __init__(self):
        self.contain_message_attri = False
        self.contain_signal_attri = False
        self.contain_value_decription = False
        self.contain_comment = False
        self.n_message_attri = 0
        self.n_signal_attri = 0
        self.message_attribute_name_list = []
        self.signal_attribute_name_list = []
        self.message_attribute_defualt_value_list = []
        self.signal_attribute_defualt_value_list = []



class Record(object):
    def __init__(self, line, config):

        row_list = line.strip().split(',')

        self.message_id, self.isExtend, self.message_name, self.message_size, self.transmitter = row_list[0:5]
        self.message_attri = []
        for i in range(0, config.n_message_attri):
            self.message_attri.append(row_list[i+5])
        index = 5+config.n_message_attri
        # receiver,signal_name,mutiplexer_flag,mutiplexer_switch_value,start_bit,signal_size,byte_order,value_type,factor,offset,minimum,maximum,unit,
        self.receiver_raw, self.signal_name, self.mutiplexer_flag, self.mutiplexer_switch_value, \
            self.start_bit, self.signal_size, self.byte_order, self.value_type, self.factor, self.offset, \
            self.minimum, self.maximum, self.unit = row_list[index:index+13]
        self.signal_attri = []
        for i in range(0, config.n_signal_attri):
            self.signal_attri.append(row_list[i + index+13])
        index = 5 + config.n_message_attri + 13 + config.n_signal_attri
        self.value_description = row_list[index]
        self.comment = row_list[index+1]


class Signal(object):
    def __init__(self,record):
        self.signal_name = record.signal_name
        self.mutiplexer_flag = record.mutiplexer_flag
        if self.mutiplexer_flag == 'None':
            self.mutiplexer_flag_in_dbc = ' '
        else:
            self.mutiplexer_flag_in_dbc = self.mutiplexer_flag
        self.mutiplexer_switch_value = record.mutiplexer_switch_value
        self.start_bit = int(record.start_bit)
        self.signal_size = int(record.signal_size)
        self.byte_order = record.byte_order
        if self.byte_order == 'Intel':
            self.byte_order_in_dbc = 1
        else:
            self.byte_order_in_dbc = 0
        self.value_type = record.value_type
        if self.value_type == 'unsigned':
            self.value_type_in_dbc = '+'
        else:
            self.value_type_in_dbc = '-'
        self.factor = float(record.factor)
        self.offset = float(record.offset)
        self.minimum = float(record.minimum)
        self.maximum =float( record.maximum)
        self.unit = record.unit
        self.receiver_list = record.receiver_raw.split(' ')
        self.receiver_set = set(self.receiver_list)
        self.comment = record.comment
        if self.byte_order == 'Intel':
            self.start_bit_in_dbc = self.start_bit
        else:
            self.start_bit_in_dbc = calculate_MSB_motorola(self.start_bit, self.signal_size)

        rawValueDescription = record.value_description.strip('"')
        self.ValueDescriptionList = []
        pattern = r'([-.0-9]+)\s+{([\S\s]+)}'
        if '\n' in rawValueDescription:
            rawValueDescriptionList = rawValueDescription.strip('\n').split('\n')
            # if self.signal_name == 'VSELatAcc_h2HSC2':
            #     print(self.signal_name)
            for i in range(0, len(rawValueDescriptionList)):
                m = re.match(pattern, rawValueDescriptionList[i].strip())
                # print(self.signal_name)
                assert m is not None, 'ValueDescriptionList 正则化失败'
                self.ValueDescriptionList.append([m.group(1), m.group(2)])

        self.signal_attri = record.signal_attri


class Message(object):
    def __init__(self,record):
        self.message_id = record.message_id
        self.isExtend = record.isExtend
        self.message_name = record.message_name
        self.message_size = record.message_size
        self.transmitter = record.transmitter
        self.SignalList = []
        if self.isExtend == 'True':
            self.id_in_dbc = int(self.message_id) | 0x80000000
        else:
            self.id_in_dbc = int(self.message_id)
        self.attri_list = record.message_attri


    def add_Signal(self,record):
        self.SignalList.append(Signal(record))


class AttributeDef(object):
    def __init__(self):
        self.type = ''
        self.name = ''
        self.value_type = ''
        self.rest = ''
        self.default_value = ''


def calculate_MSB_motorola(LSB, length):
    order_list = []
    for j in range(0, 8, 1):
        for i in range(7, -1, -1):
            order_list.append(j*8+i)
    for i in range(len(order_list)):
        assert LSB >=0 and LSB <=63, 'LSB 不符合条件'
        if LSB == order_list[i]:
            position = i
    MSB = order_list[position-length+1]
    return MSB


def process_row0(row0):
    attribute_def_list = []
    config = Config()
    pattern = r'message_id,isExtend,message_name,message_size,transmitter,([A-Za-z0-9(),_]*),?' \
              r'receiver,signal_name,mutiplexer_flag,mutiplexer_switch_value,start_bit,' \
              r'signal_size,byte_order,value_type,factor,offset,minimum,maximum,unit,([A-Za-z0-9(),_]*)'
    m = re.match(pattern, row0)
    assert m is not None, 'Row0 正则化失败'
    message_attri_def_list = m.group(1).strip(',').split(',')
    if len(message_attri_def_list) != 0:
        config.contain_message_attri = True
        for message_attri_def in message_attri_def_list:
            pattern = r'(\w+)\((\w+)\)'
            mm = re.match(pattern, message_attri_def)
            attri_def = AttributeDef()
            attri_def.type = 'BO_'
            attri_def.name = mm.group(1).strip()
            attri_def.value_type = mm.group(2).strip()
            if attri_def.value_type == 'STRING':
                attri_def.default_value = '""'
            elif attri_def.value_type == 'ENUM':
                attri_def.default_value = r'"e1"'
            else:
                attri_def.default_value = str(0)
            attribute_def_list.append(attri_def)
            config.message_attribute_name_list.append(attri_def.name)
            config.message_attribute_defualt_value_list.append(attri_def.default_value)
    else:
        config.contain_message_attri = False
    config.n_message_attri = len(attribute_def_list)

    rest = m.group(2).split(',')
    if 'comment' in rest:
        config.contain_comment = True
    else:
        config.contain_comment = False

    if 'value_description' in rest:
        config.contain_value_decription = True
    else:
        config.contain_value_decription = False

    if config.contain_comment is True and config.contain_value_decription is True and len(rest) >= 3:
        config.contain_signal_attri = True
    elif ((not config.contain_comment and config.contain_value_decription) or
              (config.contain_comment and not config.contain_value_decription))and len(rest) >= 2:
        config.contain_signal_attri = True
    elif config.contain_comment is False and config.contain_value_decription is False and len(rest) >= 1:
        config.contain_signal_attri = True
    else:
        config.contain_signal_attri = False

    if config.contain_signal_attri is True:
        for string in rest:
            if string != 'comment' and string != 'value_description':
                pattern = r'(\w+)\((\w+)\)'
                m = re.match(pattern, string)
                attri_def = AttributeDef()
                attri_def.type = 'SG_'
                attri_def.name = m.group(1).strip()
                attri_def.value_type = m.group(2).strip()
                if attri_def.value_type == 'STRING':
                    attri_def.default_value = '""'
                elif attri_def.value_type == 'ENUM':
                    attri_def.default_value = r'"e1"'
                else:
                    attri_def.default_value = str(0)
                attribute_def_list.append(attri_def)
                config.signal_attribute_name_list.append(attri_def.name)
                config.signal_attribute_defualt_value_list.append(attri_def.default_value)
    config.n_signal_attri = len(attribute_def_list) - config.n_message_attri
    return config, attribute_def_list


def process_csv_lines(csv_lines):
    processed_lines = []
    temp_line = []
    for line in csv_lines:
        temp_line.extend(line)
        if (temp_line.count('"') % 2) == 0:
            processed_lines.append(temp_line)
            temp_line = []
    return processed_lines

    
def process_csv(csv_fp):
    row0 = csv_fp.readline().strip()
    config, attribute_def_list = process_row0(row0)
    csv_lines = csv_fp.readlines()
    processed_lines = process_csv_lines(csv_lines)
    record_list = []
    for line in processed_lines:
        line = ''.join(line).strip()
        record_list.append(Record(line, config))

    message_list = []
    message_id_list = []
    for record in record_list:
        if record.message_id not in message_id_list:
            message_list.append(Message(record))
            message_id_list.append(record.message_id)
        message_list[message_id_list.index(record.message_id)].add_Signal(record)
    return config, attribute_def_list, message_list


def obtainNode(message_list):
    nodeSet=set()
    for message in message_list:
        if message.transmitter not in nodeSet:
            nodeSet.add(message.transmitter)
        for signal in message.SignalList:
            nodeSet = nodeSet.union(signal.receiver_set)
    if 'Vector__XXX' in nodeSet:
        nodeSet.remove('Vector__XXX')
    return nodeSet


def write_dbc(dbc_name, config, attribute_def_list, message_list ):
    with open(dbc_name + '_g.dbc', 'w') as dbc_fp:
        # 写文件头
        dbc_fp.write("VERSION \"\"\n")
        dbc_fp.write("\n\n")
        dbc_fp.write("NS_ : \n")
        dbc_fp.write("\tNS_DESC_\n")
        dbc_fp.write("\tCM_\n")
        dbc_fp.write("\tBA_DEF_\n")
        dbc_fp.write("\tBA_\n")
        dbc_fp.write("\tVAL_\n")
        dbc_fp.write("\tCAT_DEF_\n")
        dbc_fp.write("\tCAT_\n")
        dbc_fp.write("\tFILTER\n")
        dbc_fp.write("\tBA_DEF_DEF_\n")
        dbc_fp.write("\tEV_DATA_\n")
        dbc_fp.write("\tENVVAR_DATA_\n")
        dbc_fp.write("\tSGTYPE_\n")
        dbc_fp.write("\tSGTYPE_VAL_\n")
        dbc_fp.write("\tBA_DEF_SGTYPE_\n")
        dbc_fp.write("\tBA_SGTYPE_\n")
        dbc_fp.write("\tSIG_TYPE_REF_\n")
        dbc_fp.write("\tVAL_TABLE_\n")
        dbc_fp.write("\tSIG_GROUP_\n")
        dbc_fp.write("\tSIG_VALTYPE_\n")
        dbc_fp.write("\tSIGTYPE_VALTYPE_\n")
        dbc_fp.write("\tBO_TX_BU_\n")
        dbc_fp.write("\tBA_DEF_REL_\n")
        dbc_fp.write("\tBA_REL_\n")
        dbc_fp.write("\tBA_DEF_DEF_REL_\n")
        dbc_fp.write("\tBU_SG_REL_\n")
        dbc_fp.write("\tBU_EV_REL_\n")
        dbc_fp.write("\tBU_BO_REL_\n")
        dbc_fp.write("\tSG_MUL_VAL_\n")
        dbc_fp.write("\n")
        dbc_fp.write("BS_:\n")
        dbc_fp.write("\n")
        dbc_fp.write("BU_:")
        nodeSet=obtainNode(message_list)
        for node in nodeSet:
            dbc_fp.write(' %s' % node)
        dbc_fp.write('\n\n\n')
        # 写message和signal
        for message in message_list:
            dbc_fp.write('BO_ %u %s: %s %s\n' %
                         (message.id_in_dbc, message.message_name, message.message_size, message.transmitter))
            for signal in message.SignalList:
                dbc_fp.write(r' SG_ %s %s%s : %d|%d@%d%c (%g,%g) [%g|%g] "%s" ' % (
                    signal.signal_name,
                    signal.mutiplexer_flag_in_dbc,
                    signal.mutiplexer_switch_value,
                    signal.start_bit_in_dbc,
                    signal.signal_size,
                    signal.byte_order_in_dbc,
                    signal.value_type_in_dbc,
                    signal.factor,
                    signal.offset,
                    signal.minimum,
                    signal.maximum,
                    signal.unit))
                dbc_fp.write(','.join(signal.receiver_list)+'\n')
            dbc_fp.write('\n')
        # 写Comment
        for message in message_list:
            for signal in message.SignalList:
                if 0 != len(signal.comment.strip('"')):
                    dbc_fp.write('CM_ SG_ %u %s "%s"' % (message.id_in_dbc, signal.signal_name, signal.comment.strip('"')))
                    dbc_fp.write(';\n')

        # 写attribute_value_def
        for attribute_def in attribute_def_list:
            dbc_fp.write(r'BA_DEF_ %s  "%s" %s' % (attribute_def.type, attribute_def.name, attribute_def.value_type))
            if attribute_def.value_type == 'INT' or attribute_def.value_type == 'FLOAT':
                dbc_fp.write(r' 0 300000')
            elif attribute_def.value_type == 'STRING':
                dbc_fp.write(r'')
            elif attribute_def.value_type == 'ENUM':
                temp_list = []
                dbc_fp.write(r' ')
                for i in range(0, 10):
                    temp = r'"e' + str(i) + r'"'
                    temp_list.append(temp)
                dbc_fp.write(','.join(temp_list))
            else:
                print('无法识别attri类型')
            dbc_fp.write(';\n')
        dbc_fp.write('\n')
        # 写attribute_value_def default value
        for attribute_def in attribute_def_list:
            dbc_fp.write(r'BA_DEF_DEF_ "%s" %s' % (attribute_def.name, attribute_def.default_value))
            dbc_fp.write(';\n')
        dbc_fp.write('\n')
        # 写attribute_value
        for message in message_list:
            for i in range(0, len(message.attri_list)):
                if config.message_attribute_defualt_value_list[i] != message.attri_list[i]:
                    dbc_fp.write(r'BA_ "%s" BO_ %u %s' % (
                    config.message_attribute_name_list[i], message.id_in_dbc, message.attri_list[i]))
                    dbc_fp.write(';\n')
        for message in message_list:
            for signal in message.SignalList:
                for i in range(0, len(signal.signal_attri)):
                    if config.signal_attribute_defualt_value_list[i] != signal.signal_attri[i]:
                        dbc_fp.write(r'BA_ "%s" SG_ %u %s %s' % (config.signal_attribute_name_list[i], message.id_in_dbc, signal.signal_name, signal.signal_attri[i]))
                        dbc_fp.write(';\n')
        dbc_fp.write('\n')
        # 写value description
        for message in message_list:
            for signal in message.SignalList:
                if 0 != len(signal.ValueDescriptionList):
                    dbc_fp.write('VAL_ %u %s ' % (message.id_in_dbc, signal.signal_name))
                    for ValueDescription in signal.ValueDescriptionList:
                        dbc_fp.write(r'%d "%s" ' % (int(ValueDescription[0]), ValueDescription[1]))
                    dbc_fp.write(';\n')


def csv2dbc(csv_name):
    """
        简介：
            用于将csv转为dbc，filename.dbc生成filename_g.csv
        输入定义：

                csv_name：csv文件名，不包含后缀名，即.之前的部分
        作者信息：
            Wang Yu, wangyu_1988@126.com
        版本号：
            1.0 20160401
    """
    with open(csv_name + '.csv', 'r') as csv_fp:
        config, attribute_def_list, message_list = process_csv(csv_fp)
        write_dbc(csv_name, config, attribute_def_list, message_list)
    return


if __name__ == "__main__":
    csv_name = 'test2_g'
    csv2dbc(csv_name)
