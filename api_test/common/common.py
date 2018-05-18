import django
import sys
import os

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
PathProject = os.path.split(rootPath)[0]
sys.path.append(rootPath)
sys.path.append(PathProject)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_automation_test.settings")
django.setup()

from crontab import CronTab
from django.contrib.auth.models import User
from rest_framework.views import exception_handler

from api_test.common import GlobalStatusCode
from api_test.common.api_response import JsonResponse
from api_test.models import AutomationTestResult, AutomationCaseApi, ProjectDynamic, Project, AutomationResponseJson, \
    AutomationCaseTestResult


def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)
    # Now add the HTTP status code to the response.
    if response is not None:
        try:
            response.data['code'] = response.status_code
            response.data['msg'] = response.data['detail']
            #   response.data['data'] = None #可以存在
            # 删除detail字段
            del response.data['detail']
        except KeyError:
            for k, v in dict(response.data).items():
                if v == ['无法使用提供的认证信息登录。']:
                    if response.status_code == 400:
                        response.status_code = 200
                    response.data = {}
                    response.data['code'] = '999984'
                    response.data['msg'] = '账号或密码错误'
                elif v == ['该字段是必填项。']:
                    if response.status_code == 400:
                        response.status_code = 200
                    response.data = {}
                    response.data['code'] = '999996'
                    response.data['msg'] = '参数有误'

    return response


def verify_parameter(expect_parameter, method):
    """
    参数验证装饰器
    :param expect_parameter: 期望参数列表
    :param method: 方式
    :return:
    """
    def api(func):
        def verify(reality_parameter):
            """
            :param reality_parameter: 实际参数
            :return:
            """
            if method == 'POST':
                parameter = dict(reality_parameter.POST.lists())
            elif method == 'GET':
                parameter = dict(reality_parameter.GET.lists())
            else:
                raise Exception
            if set(expect_parameter).issubset(list(parameter)):
                for i in expect_parameter:
                    if parameter[i] == ['']:
                        return JsonResponse(code_msg=GlobalStatusCode.parameter_wrong())
            else:
                return JsonResponse(code_msg=GlobalStatusCode.parameter_wrong())

            return func(reality_parameter)
        return verify
    return api


result = 'success'


def check_json(src_data, dst_data):
    """
    校验的json
    :param src_data:  校验内容
    :param dst_data:  接口返回的数据（被校验的内容
    :return:
    """
    global result
    try:
        if isinstance(src_data, dict):
            """若为dict格式"""
            for key in src_data:
                if key not in dst_data:
                    result = 'fail'
                else:
                    # if src_data[key] != dst_data[key]:
                    #     result = False
                    this_key = key
                    """递归"""
                    if isinstance(src_data[this_key], dict) and isinstance(dst_data[this_key], dict):
                        check_json(src_data[this_key], dst_data[this_key])
                    elif isinstance(type(src_data[this_key]), type(dst_data[this_key])):
                        result = 'fail'
                    else:
                        pass
            return result
        return 'fail'

    except Exception as e:
        return 'fail'


def record_results(_id, url, request_type, header, parameter, host,
                   status_code, examine_type, examine_data, _result, code, response_data):
    """
    记录手动测试结果
    :param _id: ID
    :param url:  请求地址
    :param request_type:  请求方式
    :param header: 请求头
    :param parameter: 请求参数
    :param status_code: 期望HTTP状态
    :param examine_type: 校验方式
    :param examine_data: 校验内容
    :param _result:  是否通过
    :param code:  HTTP状态码
    :param response_data:  返回结果
    :param host:  测试地址
    :return:
    """
    rt = AutomationTestResult.objects.filter(automationCaseApi=_id)
    if rt:
        rt.update(url=url, requestType=request_type, header=header, parameter=parameter, host=host,
                  statusCode=status_code, examineType=examine_type, data=examine_data,
                  result=_result, httpStatus=code, responseData=response_data)
    else:
        result_ = AutomationTestResult(automationCaseApi=AutomationCaseApi.objects.get(id=_id), host=host,
                                       url=url, requestType=request_type, header=header, parameter=parameter,
                                       statusCode=status_code, examineType=examine_type, data=examine_data,
                                       result=_result, httpStatus=code, responseData=response_data)
        result_.save()


def record_auto_results(_id, time,  header, parameter, _result, code, response_data):
    """
    记录自动测试结果
    :param _id: ID
    :param time:  测试时间
    :param header: 请求头
    :param parameter: 请求参数
    :param _result:  是否通过
    :param code:  HTTP状态码
    :param response_data:  返回结果
    :return:
    """
    result_ = AutomationCaseTestResult(automationCaseApi=AutomationCaseApi.objects.get(id=_id), header=header,
                                       parameter=parameter, testTime=time,
                                       result=_result, httpStatus=code, responseData=response_data)
    result_.save()


def record_dynamic(project_id, _type, _object, desc):
    """
    记录动态
    :param project_id:  项目ID
    :param _type:  操作类型
    :param _object:  操作对象
    :param desc:  描述
    :return:
    """
    record = ProjectDynamic(project=Project.objects.get(id=project_id), type=_type,
                            operationObject=_object, user=User.objects.get(id=1),
                            description=desc)
    record.save()


def create_json(api_id, api, data):
    """
    根据json数据生成关联数据接口
    :param api_id: 接口ID
    :param data: Json数据
    :param api: 格式化api数据
    :return:
    """
    if isinstance(data, dict):
        for i in data:
            m = (api+"[\"%s\"]" % i)
            AutomationResponseJson(automationCaseApi=api_id, name=i, tier=m).save()
            create_json(api_id, m, data[i])


def del_task_crontab(project):
    my_user_cron = CronTab(user=True)
    my_user_cron.remove_all(comment=project)
    my_user_cron.remove_all(comment=project+"_开始")
    my_user_cron.remove_all(comment=project+"_结束")
    my_user_cron.write()
