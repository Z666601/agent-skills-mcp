'use strict';
const MINIMAL = [
  ...'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
  ...'abcdefghijklmnopqrstuvwxyz',
  ...'0123456789',
  ...`.,;:!?'"-()@#&+/$`,
];
const SPANISH = [...MINIMAL, ...'ÑñÁÉÍÓÚáéíóúü¿¡'];

// added: 实习周记手写字符集（顺序与字帖PDF一致）
const JOURNAL = [...'0123456789，。、；：！？（）《》“”‘’—…·-.~%ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz实习周记第目的要求内容体会总结收获本到公司单位部门岗师傅带教老同事领导前辈安排任务学工作熟悉适应环境规章制度认真踏主动请问题录笔电脑设备维护软件硬网络装卸载修检查故障处理解决方法步骤流程简复杂困难挑战顺利完成为了提高效率质量时间进计划汇报沟通协团队个人能力知识技论际合差距发现改升积累经验训长感谢帮助指一是我不在他有这上们来大地子中你说生国年着就那和她出也得里后自以家可下而过天去对小多然于心么之都好看起当没只如把还用样道想种开美从无情己面最女但些所日手又行意期它头儿回分爱因很给名斯世什两次使身者被已亲其此话常与活正智微术员数据管班级院帅泽霖系统运办打印机卡顿死蓝屏重启账号密码权限表格文档云仓库存考勤培议告材料签字盖交截止拖延补注填写范整洁'];
module.exports = { CHARSETS: { minimal: MINIMAL, spanish: SPANISH, journal: JOURNAL } };
