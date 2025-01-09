import wandb

sweep_config = {
    'method': 'random'
    }

metric = {
    'name': 'loss',
    'goal': 'minimize'   
    }

sweep_config['metric'] = metric

parameters_dict = {
    #'weight_decay': {
    #      []
     # },
    #'optimizer': {
    #    'values': ['adam', 'sgd']
    #    },
    'hidden_layers': {
        'values': [64, 128, 256] #32, 512
        },
'dropout': {
          'values': [0.3, 0.4, 0.5]
        },
'k': {
          'values': [2, 3, 4, 5, 6]
        },
'wd': {
          'values': [1e-05, 1e-06, 1e-07, 1e-08, 1e-09]
        },
'attention_heads': {
          'values': [2, 3, 4, 5]
        },
    }

sweep_config['parameters'] = parameters_dict

#parameters_dict.update({
#    'epochs': {
 #       'value': 1}
 #   })

#parameters_dict.update({
#    'batch_size': {
#        # integers between 32 and 256
 #       # with evenly-distributed logarithms 
#        'distribution': 'q_log_uniform_values',
#        'q': 8,
 #       'min': 32,
 #       'max': 256,
 #     }
 #   })