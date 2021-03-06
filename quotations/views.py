from django.contrib import messages
from django.core.urlresolvers import reverse
from django.forms.models import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render_to_response
from django.template import RequestContext

from contacts.models import ContactList
from customers.forms import CustomerForm
from customers.models import Customer
from histories.models import History
from quotations.forms import QuotationForm
from quotations.models import Quotation
from utils.tools import render_to_pdf


def index(request):
    quotations = Quotation.objects.all()

    data = {
        'quotations': quotations,
    }

    return render_to_response(
        'quotations/index.html',
        data,
        context_instance=RequestContext(request),
    )


def customer(request):
    customers = Customer.objects.all()

    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            History.created_history(customer, request.user)
            return redirect('quotations:create', customer.pk)
    else:
        form = CustomerForm()

    data = {
        'customers': customers,
        'form': form,
    }

    return render_to_response(
        'quotations/customer.html',
        data,
        context_instance=RequestContext(request),
    )


def create(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == 'POST':
        contacts = ContactList.post_dict(request.POST)
        form = QuotationForm(request.POST)
        if form.is_valid():
            quotation = form.save()
            msg = quotation.contact_list.update_contacts(contacts)
            if msg:
                messages.warning(request, msg)
            else:
                messages.success(request, 'Customer created')

            History.created_history(quotation, request.user)
            messages.success(request, 'Quotation created.')
            return redirect('quotations:update', quotation.pk)
    else:
        contacts = {}
        form = QuotationForm(initial={'customer': customer_id})

    data = {
        'contacts': contacts,
        'form': form,
    }

    return render_to_response(
        'quotations/create.html',
        data,
        context_instance=RequestContext(request),
    )


def update(request, quotation_id):
    quotation = get_object_or_404(Quotation, pk=quotation_id)

    if request.method == 'POST':
        if 'convert-to-cash-sale' in request.POST:
           cash_sale = quotation.to_cash_sale()
           return redirect('sales:update', 'cash', cash_sale.pk)
        elif 'convert-to-credit-sale' in request.POST:
           credit_sale = quotation.to_credit_sale()
           return redirect('sales:update', 'credit', credit_sale.pk)

        contacts = quotation.contact_list.post_dict(request.POST)
        form = QuotationForm(request.POST, instance=quotation)
        stock_item_code = request.POST.get('stock-item-code', '')
        
        if stock_item_code:
            msg = quotation.cart.add_item(stock_item_code)
            if msg.get('success', ''):
                messages.success(request, msg.get('success', ''))
            else:
                messages.warning(request, msg.get('warning', ''))
        else:
            if form.is_valid():
                form.save()
                quotation.cart.update_items(request.POST)
                messages.success(request, 'Quotation updated.')

        msg = quotation.contact_list.update_contacts(contacts)
        if msg:
            messages.warning(request, msg)
    else:
        try:
            contacts = quotation.contact_list.get_dict()
        except AttributeError:
            quotation.save()
            contacts = {}
        form = QuotationForm(instance=quotation)

    stock_items = quotation.cart.stockcartitem_set.all()

    data = {
        'cart': quotation.cart,
        'contacts': contacts,
        'form': form,
        'price_type': quotation.customer.price_type,
        'quotation': quotation,
        'stock_items': stock_items,
    }

    return render_to_response(
        'quotations/update.html',
        data,
        context_instance=RequestContext(request),
    )


def delete(request):
    quotation_id = int(request.POST.get('entry_id', 0))
    try:
        quotation = Quotation.objects.get(pk=quotation_id)
        quotation.delete() 
        messages.success(request, 'Quotation deleted')
    except Quotation.DoesNotExist:
        messages.error(request, 'Quotation with id %i does not exist' % quotation_id)
    data = reverse('quotations:index')
    return HttpResponse(data, mimetype="application/javascript")


def invoice(request, quotation_id):
    quotation = get_object_or_404(Quotation, pk=quotation_id)
    try:
        contacts = quotation.contact_list.get_dict()
    except AttributeError:
        quotation.save()
        contacts = {}
    stock_items = quotation.cart.stockcartitem_set.all()

    data = {
        'cart': quotation.cart,
        'contacts': contacts,
        'price_type': quotation.customer.price_type,
        'quotation': quotation,
        'stock_items': stock_items,
    }

    if 'pdf' in request.GET:
        return render_to_pdf('invoices/quotation.html', data, 'quotation')

    return render_to_response(
        'invoices/quotation.html',
        data,
        context_instance=RequestContext(request),
    )
